#!/bin/bash
# Quick Fix for PKG_CONFIG_PATH Issue
# This is the #1 reason GStreamer isn't detected by CMake on Jetson

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Quick Fix: PKG_CONFIG_PATH for GStreamer             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Step 1: Verify GStreamer is installed
# ============================================================================

echo -e "${YELLOW}Step 1: Checking if GStreamer packages are installed...${NC}"

if ! dpkg -l | grep -q libgstreamer1.0-dev; then
    echo -e "${RED}✗ libgstreamer1.0-dev not installed${NC}"
    echo ""
    echo "Installing GStreamer development packages..."
    sudo apt-get update
    sudo apt-get install -y \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        pkg-config
    echo -e "${GREEN}✓ Installed${NC}"
else
    echo -e "${GREEN}✓ GStreamer packages already installed${NC}"
fi

echo ""

# ============================================================================
# Step 2: Find where .pc files are located
# ============================================================================

echo -e "${YELLOW}Step 2: Locating GStreamer .pc files...${NC}"

PC_FILE=$(find /usr/lib -name "gstreamer-1.0.pc" 2>/dev/null | head -1)

if [ -z "$PC_FILE" ]; then
    echo -e "${RED}✗ Cannot find gstreamer-1.0.pc${NC}"
    echo ""
    echo "This means GStreamer development files are not properly installed."
    echo "Try: sudo apt-get install --reinstall libgstreamer1.0-dev"
    exit 1
fi

PC_DIR=$(dirname "$PC_FILE")
echo -e "${GREEN}✓ Found: $PC_FILE${NC}"
echo "  Directory: $PC_DIR"
echo ""

# ============================================================================
# Step 3: Set PKG_CONFIG_PATH
# ============================================================================

echo -e "${YELLOW}Step 3: Setting PKG_CONFIG_PATH...${NC}"

# Check if already set
if echo "$PKG_CONFIG_PATH" | grep -q "$PC_DIR"; then
    echo -e "${GREEN}✓ PKG_CONFIG_PATH already includes $PC_DIR${NC}"
else
    # Add to current session
    export PKG_CONFIG_PATH="$PC_DIR:$PKG_CONFIG_PATH"
    echo -e "${GREEN}✓ Set for current session${NC}"
    
    # Add to ~/.bashrc for permanent fix
    if ! grep -q "PKG_CONFIG_PATH.*$PC_DIR" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# GStreamer pkg-config path (added by fix script)" >> ~/.bashrc
        echo "export PKG_CONFIG_PATH=\"$PC_DIR:\$PKG_CONFIG_PATH\"" >> ~/.bashrc
        echo -e "${GREEN}✓ Added to ~/.bashrc (permanent)${NC}"
    else
        echo -e "${GREEN}✓ Already in ~/.bashrc${NC}"
    fi
fi

echo ""
echo "Current PKG_CONFIG_PATH:"
echo "  $PKG_CONFIG_PATH"
echo ""

# ============================================================================
# Step 4: Verify pkg-config can find GStreamer
# ============================================================================

echo -e "${YELLOW}Step 4: Testing pkg-config...${NC}"

if pkg-config --exists gstreamer-1.0; then
    VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo -e "${GREEN}✓ pkg-config found GStreamer ${VERSION}${NC}"
else
    echo -e "${RED}✗ pkg-config still can't find GStreamer${NC}"
    echo ""
    echo "Debug info:"
    echo "  PKG_CONFIG_PATH = $PKG_CONFIG_PATH"
    echo "  .pc file exists = $([ -f "$PC_FILE" ] && echo 'yes' || echo 'no')"
    exit 1
fi

echo ""
echo -n "Testing pkg-config --cflags... "
if CFLAGS=$(pkg-config --cflags gstreamer-1.0 2>/dev/null); then
    echo -e "${GREEN}✓${NC}"
    echo "  $CFLAGS" | cut -c1-60
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

echo -n "Testing pkg-config --libs... "
if LIBS=$(pkg-config --libs gstreamer-1.0 2>/dev/null); then
    echo -e "${GREEN}✓${NC}"
    echo "  $LIBS" | cut -c1-60
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# ============================================================================
# Step 5: Test with all required GStreamer components
# ============================================================================

echo ""
echo -e "${YELLOW}Step 5: Checking all GStreamer components...${NC}"

REQUIRED_COMPONENTS=(
    "gstreamer-1.0"
    "gstreamer-base-1.0"
    "gstreamer-video-1.0"
    "gstreamer-app-1.0"
)

ALL_OK=1
for component in "${REQUIRED_COMPONENTS[@]}"; do
    echo -n "  $component... "
    if pkg-config --exists "$component"; then
        VERSION=$(pkg-config --modversion "$component")
        echo -e "${GREEN}✓ ${VERSION}${NC}"
    else
        echo -e "${RED}✗ NOT FOUND${NC}"
        ALL_OK=0
    fi
done

if [ $ALL_OK -eq 0 ]; then
    echo ""
    echo -e "${YELLOW}Some components missing. Installing...${NC}"
    sudo apt-get install -y \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-good1.0-dev
    echo -e "${GREEN}✓ Installed${NC}"
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  FIX SUCCESSFUL!                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "PKG_CONFIG_PATH has been set to: $PC_DIR"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Source the updated bashrc (for permanent fix):"
echo -e "   ${YELLOW}source ~/.bashrc${NC}"
echo ""
echo "2. If you're building OpenCV, clean the CMake cache:"
echo -e "   ${YELLOW}cd ~/opencv_build/opencv/build${NC}"
echo -e "   ${YELLOW}rm -rf *${NC}"
echo ""
echo "3. Re-run CMake (it should detect GStreamer now):"
echo -e "   ${YELLOW}cmake -D CMAKE_BUILD_TYPE=Release \\
     -D WITH_GSTREAMER=ON \\
     -D WITH_CUDA=ON \\
     -D BUILD_opencv_python3=ON \\
     -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \\
     ..${NC}"
echo ""
echo "4. Verify GStreamer is detected:"
echo -e "   ${YELLOW}grep -i gstreamer CMakeCache.txt${NC}"
echo ""
echo "   Should show: ${GREEN}WITH_GSTREAMER:BOOL=ON${NC}"
echo ""

# Create helper script
cat > ~/test_gstreamer_pkgconfig.sh << 'EOF'
#!/bin/bash
# Quick test script to verify GStreamer pkg-config works

echo "Testing GStreamer pkg-config detection..."
echo ""

if pkg-config --exists gstreamer-1.0; then
    echo "✓ GStreamer found"
    echo "  Version: $(pkg-config --modversion gstreamer-1.0)"
    echo "  Cflags: $(pkg-config --cflags gstreamer-1.0 | cut -c1-60)..."
    echo "  Libs: $(pkg-config --libs gstreamer-1.0 | cut -c1-60)..."
else
    echo "✗ GStreamer NOT found"
    echo "  PKG_CONFIG_PATH = $PKG_CONFIG_PATH"
    exit 1
fi

echo ""
echo "All GStreamer components:"
for pkg in gstreamer-1.0 gstreamer-base-1.0 gstreamer-video-1.0 gstreamer-app-1.0; do
    if pkg-config --exists $pkg; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg"
    fi
done
EOF

chmod +x ~/test_gstreamer_pkgconfig.sh

echo -e "${GREEN}Created test script: ~/test_gstreamer_pkgconfig.sh${NC}"
echo "Run it anytime to verify GStreamer detection: ./test_gstreamer_pkgconfig.sh"
echo ""