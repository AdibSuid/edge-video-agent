#!/bin/bash
# Bulletproof OpenCV Build Script for Jetson with GStreamer
# Automatically detects and fixes issues during build

set -e

OPENCV_VERSION="4.8.0"
BUILD_DIR="$HOME/opencv_build"
NUM_JOBS=$(nproc)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Bulletproof OpenCV ${OPENCV_VERSION} Build for Jetson          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Phase 1: Comprehensive Dependency Installation
# ============================================================================

echo -e "${BLUE}Phase 1: Installing ALL Dependencies${NC}"
echo ""

sudo apt-get update

echo -e "${GREEN}[1/5] Installing build tools...${NC}"
sudo apt-get install -y build-essential cmake git wget unzip pkg-config

echo -e "${GREEN}[2/5] Installing GStreamer (COMPREHENSIVE)...${NC}"
sudo apt-get install -y \
    libgstreamer1.0-0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

echo -e "${GREEN}[3/5] Installing video/image libraries...${NC}"
sudo apt-get install -y \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk-3-dev libatlas-base-dev gfortran

echo -e "${GREEN}[4/5] Installing Python development...${NC}"
sudo apt-get install -y python3-dev python3-numpy python3-pip

echo -e "${GREEN}[5/5] Installing additional tools...${NC}"
sudo apt-get install -y libtbb-dev libdc1394-22-dev

# Verify GStreamer pkg-config
echo ""
echo -e "${YELLOW}Verifying GStreamer installation...${NC}"
if pkg-config --exists gstreamer-1.0; then
    GST_VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo -e "${GREEN}✓ GStreamer ${GST_VERSION} detected${NC}"
else
    echo -e "${RED}✗ GStreamer pkg-config not found!${NC}"
    echo ""
    echo "Attempting to fix..."
    
    # Try to locate .pc files
    PC_PATH=$(find /usr/lib -name "gstreamer-1.0.pc" 2>/dev/null | head -1 | xargs dirname)
    if [ -n "$PC_PATH" ]; then
        echo "Found .pc files at: $PC_PATH"
        export PKG_CONFIG_PATH="$PC_PATH:$PKG_CONFIG_PATH"
        echo "export PKG_CONFIG_PATH=\"$PC_PATH:\$PKG_CONFIG_PATH\"" >> ~/.bashrc
        echo -e "${GREEN}✓ Fixed PKG_CONFIG_PATH${NC}"
    else
        echo -e "${RED}Cannot locate gstreamer-1.0.pc file${NC}"
        echo "Run: sudo apt-get install --reinstall libgstreamer1.0-dev"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✓ All dependencies installed${NC}"

# ============================================================================
# Phase 2: Download OpenCV Source
# ============================================================================

echo ""
echo -e "${BLUE}Phase 2: Downloading OpenCV Source${NC}"
echo ""

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [ ! -d "opencv" ]; then
    echo -e "${GREEN}Downloading opencv ${OPENCV_VERSION}...${NC}"
    wget -q --show-progress -O opencv.zip \
        https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip
    unzip -q opencv.zip
    mv opencv-${OPENCV_VERSION} opencv
    rm opencv.zip
else
    echo "OpenCV source already exists"
fi

if [ ! -d "opencv_contrib" ]; then
    echo -e "${GREEN}Downloading opencv_contrib ${OPENCV_VERSION}...${NC}"
    wget -q --show-progress -O opencv_contrib.zip \
        https://github.com/opencv/opencv_contrib/archive/${OPENCV_VERSION}.zip
    unzip -q opencv_contrib.zip
    mv opencv_contrib-${OPENCV_VERSION} opencv_contrib
    rm opencv_contrib.zip
else
    echo "OpenCV contrib already exists"
fi

echo -e "${GREEN}✓ Source code ready${NC}"

# ============================================================================
# Phase 3: Configure with CMake (WITH RETRY LOGIC)
# ============================================================================

echo ""
echo -e "${BLUE}Phase 3: Configuring Build with CMake${NC}"
echo ""

cd opencv
mkdir -p build
cd build

# Clean any previous cache
rm -rf *

# Source bashrc to get updated PKG_CONFIG_PATH
source ~/.bashrc 2>/dev/null || true

echo -e "${YELLOW}Running CMake (this takes a few minutes)...${NC}"
echo ""

# Run CMake with comprehensive flags
cmake \
    -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="5.3,6.2,7.2,8.7" \
    -D CUDA_ARCH_PTX="" \
    -D WITH_CUBLAS=ON \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D PYTHON3_INCLUDE_DIR=$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))") \
    -D PYTHON3_PACKAGES_PATH=$(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))") \
    \
    -D WITH_V4L=ON \
    -D WITH_LIBV4L=ON \
    -D WITH_GTK=ON \
    -D WITH_QT=OFF \
    -D WITH_OPENGL=ON \
    -D WITH_TBB=ON \
    \
    -D BUILD_JPEG=ON \
    -D BUILD_PNG=ON \
    -D BUILD_TIFF=ON \
    -D WITH_FFMPEG=ON \
    \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
    \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_DOCS=OFF \
    \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    \
    -D PKG_CONFIG_EXECUTABLE=/usr/bin/pkg-config \
    ..

CMAKE_RESULT=$?

if [ $CMAKE_RESULT -ne 0 ]; then
    echo -e "${RED}✗ CMake configuration failed!${NC}"
    echo ""
    echo "Checking CMake error log..."
    if [ -f "CMakeFiles/CMakeError.log" ]; then
        echo ""
        echo "=== Last 30 lines of CMakeError.log ==="
        tail -30 CMakeFiles/CMakeError.log
    fi
    exit 1
fi

echo ""
echo -e "${YELLOW}Checking GStreamer detection...${NC}"

if grep -q "GStreamer.*YES" CMakeCache.txt 2>/dev/null; then
    echo -e "${GREEN}✓ GStreamer: ENABLED${NC}"
    GST_FOUND=1
elif grep -q "GStreamer.*NO" CMakeCache.txt 2>/dev/null; then
    echo -e "${RED}✗ GStreamer: DISABLED${NC}"
    GST_FOUND=0
else
    echo -e "${YELLOW}⚠ GStreamer status: UNKNOWN${NC}"
    GST_FOUND=0
fi

if [ $GST_FOUND -eq 0 ]; then
    echo ""
    echo -e "${RED}GStreamer was NOT detected by CMake!${NC}"
    echo ""
    echo "Possible reasons:"
    echo "1. pkg-config can't find gstreamer-1.0.pc"
    echo "2. GStreamer headers not installed"
    echo "3. PKG_CONFIG_PATH not set correctly"
    echo ""
    echo "Diagnostic information:"
    echo ""
    
    echo "=== pkg-config test ==="
    pkg-config --exists gstreamer-1.0 && echo "gstreamer-1.0: FOUND" || echo "gstreamer-1.0: NOT FOUND"
    
    echo ""
    echo "=== .pc file location ==="
    find /usr -name "gstreamer-1.0.pc" 2>/dev/null | head -5
    
    echo ""
    echo "=== PKG_CONFIG_PATH ==="
    echo "$PKG_CONFIG_PATH"
    
    echo ""
    echo "=== CMake GStreamer check ==="
    grep -A 5 "GStreamer" CMakeCache.txt | head -10
    
    echo ""
    echo -e "${YELLOW}To continue anyway, you can:${NC}"
    echo "1. Build without GStreamer (not recommended)"
    echo "2. Fix GStreamer detection and re-run this script"
    echo ""
    read -p "Continue without GStreamer? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build aborted. Please fix GStreamer detection first."
        exit 1
    fi
fi

# Show build configuration summary
echo ""
echo -e "${BLUE}═══ Build Configuration Summary ═══${NC}"
grep -E "GStreamer|CUDA|Python|Video" CMakeCache.txt | grep -v "//" | head -15
echo ""

# ============================================================================
# Phase 4: Build OpenCV
# ============================================================================

echo ""
echo -e "${BLUE}Phase 4: Building OpenCV${NC}"
echo ""

echo -e "${YELLOW}Building with ${NUM_JOBS} parallel jobs...${NC}"
echo -e "${YELLOW}This will take 30-90 minutes.${NC}"
echo ""

# Free memory before build
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# Start build
START_TIME=$(date +%s)

if make -j${NUM_JOBS} 2>&1 | tee build.log; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))
    
    echo ""
    echo -e "${GREEN}✓ Build completed in ${MINUTES}m ${SECONDS}s${NC}"
else
    echo ""
    echo -e "${RED}✗ Build failed!${NC}"
    echo ""
    echo "Checking build log for errors..."
    grep -i "error:" build.log | tail -10
    echo ""
    echo "Common fixes:"
    echo "1. Out of memory: try 'make -j2' instead"
    echo "2. Missing dependencies: re-run Phase 1"
    echo ""
    exit 1
fi

# ============================================================================
# Phase 5: Install OpenCV
# ============================================================================

echo ""
echo -e "${BLUE}Phase 5: Installing OpenCV${NC}"
echo ""

sudo make install
sudo ldconfig

echo -e "${GREEN}✓ Installation complete${NC}"

# ============================================================================
# Phase 6: Verification
# ============================================================================

echo ""
echo -e "${BLUE}Phase 6: Verification${NC}"
echo ""

echo -e "${YELLOW}Testing Python import...${NC}"
python3 -c "import cv2; print(f'OpenCV Version: {cv2.__version__}')" || {
    echo -e "${RED}✗ Failed to import cv2${NC}"
    exit 1
}

echo ""
echo -e "${YELLOW}Checking GStreamer support...${NC}"
python3 << 'EOF'
import cv2

info = cv2.getBuildInformation()

# Find GStreamer line
gst_found = False
for line in info.split('\n'):
    if 'GStreamer' in line and 'YES' in line:
        print(f'✓ {line.strip()}')
        gst_found = True
        break
    elif 'GStreamer' in line:
        print(f'✗ {line.strip()}')

if not gst_found:
    print('✗ GStreamer support NOT enabled')
    exit(1)
EOF

VERIFY_RESULT=$?

echo ""
if [ $VERIFY_RESULT -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          BUILD SUCCESSFUL WITH GSTREAMER!                 ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Use the OpenCV-based hardware accelerated streamer:"
    echo -e "   ${YELLOW}cp streamer_jetson_hw.py streamer.py${NC}"
    echo ""
    echo "2. Run your application:"
    echo -e "   ${YELLOW}python app.py${NC}"
    echo ""
    echo "3. Clean up build files (optional, saves ~2.5GB):"
    echo -e "   ${YELLOW}rm -rf $BUILD_DIR${NC}"
else
    echo -e "${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   BUILD SUCCESSFUL BUT GSTREAMER NOT ENABLED              ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "OpenCV was built but WITHOUT GStreamer support."
    echo ""
    echo "You can either:"
    echo "1. Use the native GStreamer version (recommended):"
    echo -e "   ${YELLOW}cp streamer_jetson_native.py streamer.py${NC}"
    echo ""
    echo "2. Or rebuild OpenCV after fixing GStreamer detection"
fi

echo ""
echo -e "${GREEN}Build script completed!${NC}"