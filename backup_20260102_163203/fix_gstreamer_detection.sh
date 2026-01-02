#!/bin/bash
# GStreamer Detection Diagnostic and Fix Script for OpenCV Build
# This script identifies WHY GStreamer isn't detected and fixes it

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      GStreamer Detection Diagnostic & Fix Tool            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# DIAGNOSTIC PHASE
# ============================================================================

echo -e "${YELLOW}Running diagnostics...${NC}"
echo ""

ISSUES_FOUND=0

# Check 1: pkg-config installed
echo -n "Checking pkg-config... "
if command -v pkg-config &> /dev/null; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${RED}✗ NOT installed${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_PKG_CONFIG=1
fi

# Check 2: GStreamer runtime
echo -n "Checking GStreamer runtime... "
if command -v gst-launch-1.0 &> /dev/null; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${RED}✗ NOT installed${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_RUNTIME=1
fi

# Check 3: GStreamer pkg-config files
echo -n "Checking GStreamer pkg-config... "
if pkg-config --exists gstreamer-1.0 2>/dev/null; then
    VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo -e "${GREEN}✓ found (version ${VERSION})${NC}"
else
    echo -e "${RED}✗ NOT found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_DEV=1
fi

# Check 4: GStreamer base plugins pkg-config
echo -n "Checking GStreamer base plugins... "
if pkg-config --exists gstreamer-base-1.0 2>/dev/null; then
    echo -e "${GREEN}✓ found${NC}"
else
    echo -e "${RED}✗ NOT found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_BASE=1
fi

# Check 5: GStreamer video plugin
echo -n "Checking GStreamer video plugin... "
if pkg-config --exists gstreamer-video-1.0 2>/dev/null; then
    echo -e "${GREEN}✓ found${NC}"
else
    echo -e "${RED}✗ NOT found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_VIDEO=1
fi

# Check 6: GStreamer app plugin
echo -n "Checking GStreamer app plugin... "
if pkg-config --exists gstreamer-app-1.0 2>/dev/null; then
    echo -e "${GREEN}✓ found${NC}"
else
    echo -e "${RED}✗ NOT found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_APP=1
fi

# Check 7: GStreamer header files
echo -n "Checking GStreamer headers... "
if [ -f "/usr/include/gstreamer-1.0/gst/gst.h" ]; then
    echo -e "${GREEN}✓ found${NC}"
else
    echo -e "${RED}✗ NOT found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
    NEED_GSTREAMER_HEADERS=1
fi

# Check 8: PKG_CONFIG_PATH
echo -n "Checking PKG_CONFIG_PATH... "
if [ -z "$PKG_CONFIG_PATH" ]; then
    echo -e "${YELLOW}⚠ not set${NC}"
    # Check if .pc files exist in standard location
    if [ -f "/usr/lib/aarch64-linux-gnu/pkgconfig/gstreamer-1.0.pc" ]; then
        echo -e "  ${YELLOW}Found .pc files but PKG_CONFIG_PATH not set${NC}"
        NEED_PKG_CONFIG_PATH=1
    fi
else
    echo -e "${GREEN}✓ set to: $PKG_CONFIG_PATH${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# ============================================================================
# SUMMARY
# ============================================================================

if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✓ All GStreamer components detected correctly!${NC}"
    echo ""
    echo "GStreamer should work with OpenCV. If CMake still fails:"
    echo "1. Clean CMake cache: rm -rf build && mkdir build"
    echo "2. Run CMake with verbose output: cmake .. -DCMAKE_VERBOSE_MAKEFILE=ON"
    echo "3. Check CMakeError.log in build directory"
    exit 0
else
    echo -e "${RED}Found ${ISSUES_FOUND} issue(s) that need fixing${NC}"
    echo ""
fi

# ============================================================================
# FIX PHASE
# ============================================================================

echo -e "${YELLOW}Would you like to fix these issues automatically? (y/n)${NC}"
read -p "> " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting without fixes."
    exit 1
fi

echo ""
echo -e "${BLUE}Applying fixes...${NC}"
echo ""

# Fix 1: Install pkg-config
if [ -n "$NEED_PKG_CONFIG" ]; then
    echo -e "${GREEN}Installing pkg-config...${NC}"
    sudo apt-get update
    sudo apt-get install -y pkg-config
fi

# Fix 2: Install GStreamer runtime
if [ -n "$NEED_GSTREAMER_RUNTIME" ]; then
    echo -e "${GREEN}Installing GStreamer runtime...${NC}"
    sudo apt-get install -y \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly
fi

# Fix 3-7: Install GStreamer development packages
if [ -n "$NEED_GSTREAMER_DEV" ] || [ -n "$NEED_GSTREAMER_BASE" ] || \
   [ -n "$NEED_GSTREAMER_VIDEO" ] || [ -n "$NEED_GSTREAMER_APP" ] || \
   [ -n "$NEED_GSTREAMER_HEADERS" ]; then
    
    echo -e "${GREEN}Installing GStreamer development packages...${NC}"
    
    # Remove potentially broken packages first
    sudo apt-get remove -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev 2>/dev/null || true
    
    # Clean package cache
    sudo apt-get clean
    sudo apt-get update
    
    # Install fresh
    sudo apt-get install -y \
        libgstreamer1.0-0 \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-0 \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-good1.0-dev \
        libgstreamer-plugins-bad1.0-dev
fi

# Fix 8: Set PKG_CONFIG_PATH
if [ -n "$NEED_PKG_CONFIG_PATH" ]; then
    echo -e "${GREEN}Setting PKG_CONFIG_PATH...${NC}"
    
    # Find .pc files location
    if [ -d "/usr/lib/aarch64-linux-gnu/pkgconfig" ]; then
        PC_PATH="/usr/lib/aarch64-linux-gnu/pkgconfig"
    elif [ -d "/usr/lib/arm-linux-gnueabihf/pkgconfig" ]; then
        PC_PATH="/usr/lib/arm-linux-gnueabihf/pkgconfig"
    elif [ -d "/usr/lib/pkgconfig" ]; then
        PC_PATH="/usr/lib/pkgconfig"
    fi
    
    if [ -n "$PC_PATH" ]; then
        export PKG_CONFIG_PATH="$PC_PATH:$PKG_CONFIG_PATH"
        echo "export PKG_CONFIG_PATH=\"$PC_PATH:\$PKG_CONFIG_PATH\"" >> ~/.bashrc
        echo -e "  ${GREEN}Added $PC_PATH to PKG_CONFIG_PATH${NC}"
    fi
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# ============================================================================
# VERIFICATION
# ============================================================================

echo ""
echo -e "${YELLOW}Verifying fixes...${NC}"
echo ""

VERIFICATION_PASSED=1

# Test pkg-config
echo -n "Testing pkg-config gstreamer-1.0... "
if pkg-config --exists gstreamer-1.0; then
    VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo -e "${GREEN}✓ found (${VERSION})${NC}"
else
    echo -e "${RED}✗ still not found${NC}"
    VERIFICATION_PASSED=0
fi

# Test pkg-config with cflags/libs
echo -n "Testing pkg-config --cflags... "
if pkg-config --cflags gstreamer-1.0 &> /dev/null; then
    CFLAGS=$(pkg-config --cflags gstreamer-1.0)
    echo -e "${GREEN}✓ ${CFLAGS:0:50}...${NC}"
else
    echo -e "${RED}✗ failed${NC}"
    VERIFICATION_PASSED=0
fi

echo -n "Testing pkg-config --libs... "
if pkg-config --libs gstreamer-1.0 &> /dev/null; then
    LIBS=$(pkg-config --libs gstreamer-1.0 | cut -d' ' -f1-3)
    echo -e "${GREEN}✓ ${LIBS}...${NC}"
else
    echo -e "${RED}✗ failed${NC}"
    VERIFICATION_PASSED=0
fi

# Test header file
echo -n "Testing gst/gst.h header... "
if [ -f "/usr/include/gstreamer-1.0/gst/gst.h" ]; then
    echo -e "${GREEN}✓ found${NC}"
else
    echo -e "${RED}✗ not found${NC}"
    VERIFICATION_PASSED=0
fi

# Additional diagnostics if still failing
if [ $VERIFICATION_PASSED -eq 0 ]; then
    echo ""
    echo -e "${RED}Some verifications still failing. Additional diagnostics:${NC}"
    echo ""
    
    echo "=== Installed GStreamer packages ==="
    dpkg -l | grep gstreamer
    
    echo ""
    echo "=== .pc files location ==="
    find /usr -name "gstreamer-1.0.pc" 2>/dev/null
    
    echo ""
    echo "=== Current PKG_CONFIG_PATH ==="
    echo "$PKG_CONFIG_PATH"
    
    echo ""
    echo -e "${YELLOW}Please share this output for further diagnosis.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ All fixes applied and verified successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""

# ============================================================================
# NEXT STEPS
# ============================================================================

echo -e "${BLUE}Next steps for OpenCV build:${NC}"
echo ""
echo "1. Source the updated bashrc:"
echo -e "   ${YELLOW}source ~/.bashrc${NC}"
echo ""
echo "2. Clean any previous CMake cache:"
echo -e "   ${YELLOW}cd ~/opencv_build/opencv/build${NC}"
echo -e "   ${YELLOW}rm -rf *${NC}"
echo ""
echo "3. Re-run CMake with explicit GStreamer paths:"
echo -e "   ${YELLOW}cmake \\"
echo "     -D CMAKE_BUILD_TYPE=Release \\"
echo "     -D CMAKE_INSTALL_PREFIX=/usr/local \\"
echo "     -D WITH_GSTREAMER=ON \\"
echo "     -D WITH_CUDA=ON \\"
echo "     -D BUILD_opencv_python3=ON \\"
echo "     -D PKG_CONFIG_EXECUTABLE=/usr/bin/pkg-config \\"
echo "     -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \\"
echo -e "     ..${NC}"
echo ""
echo "4. Check CMake output for GStreamer:"
echo -e "   ${YELLOW}grep -i gstreamer CMakeCache.txt${NC}"
echo ""
echo "5. If GStreamer shows YES, proceed with build:"
echo -e "   ${YELLOW}make -j\$(nproc)${NC}"
echo ""

# Create a helper script for the CMake command
cat > ~/opencv_cmake_with_gstreamer.sh << 'EOF'
#!/bin/bash
# Helper script to run CMake with GStreamer support

cd ~/opencv_build/opencv/build || exit 1

# Clean previous cache
rm -rf *

# Run CMake with GStreamer
cmake \
    -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D WITH_GSTREAMER=ON \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="5.3,6.2,7.2,8.7" \
    -D WITH_CUBLAS=ON \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D PKG_CONFIG_EXECUTABLE=/usr/bin/pkg-config \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    ..

# Check result
echo ""
echo "Checking GStreamer detection..."
if grep -q "GStreamer.*YES" CMakeCache.txt; then
    echo "✓ GStreamer: ENABLED"
    echo ""
    echo "Ready to build! Run:"
    echo "  make -j\$(nproc)"
else
    echo "✗ GStreamer: DISABLED"
    echo ""
    echo "Check CMakeError.log for details:"
    echo "  cat CMakeFiles/CMakeError.log | grep -A 20 GStreamer"
fi
EOF

chmod +x ~/opencv_cmake_with_gstreamer.sh

echo -e "${GREEN}Created helper script: ~/opencv_cmake_with_gstreamer.sh${NC}"
echo ""
echo "You can run this to configure OpenCV with GStreamer:"
echo -e "   ${YELLOW}~/opencv_cmake_with_gstreamer.sh${NC}"
echo ""