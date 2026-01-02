#!/bin/bash
# Complete OpenCV Build - Step by Step with Error Checking
# This script does EVERYTHING from scratch

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OPENCV_VERSION="4.8.0"
BUILD_DIR="$HOME/opencv_build"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Complete OpenCV ${OPENCV_VERSION} Build - From Scratch          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Step 1: Install Dependencies
# ============================================================================

echo -e "${BLUE}Step 1/7: Installing Dependencies${NC}"
echo ""

sudo apt-get update

echo "Installing build tools..."
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    pkg-config

echo "Installing GStreamer..."
sudo apt-get install -y \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-good

echo "Installing other libraries..."
sudo apt-get install -y \
    python3-dev \
    python3-numpy \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libgtk-3-dev

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# ============================================================================
# Step 2: Setup Build Directory
# ============================================================================

echo -e "${BLUE}Step 2/7: Setting Up Build Directory${NC}"
echo ""

if [ -d "$BUILD_DIR" ]; then
    echo -e "${YELLOW}Build directory exists: $BUILD_DIR${NC}"
    read -p "Remove and start fresh? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$BUILD_DIR"
        echo "Removed old build directory"
    fi
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo -e "${GREEN}✓ Build directory ready: $BUILD_DIR${NC}"
echo ""

# ============================================================================
# Step 3: Download OpenCV Source
# ============================================================================

echo -e "${BLUE}Step 3/7: Downloading OpenCV Source${NC}"
echo ""

# Download opencv
if [ ! -d "opencv" ]; then
    echo "Downloading opencv..."
    wget -q --show-progress \
        https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip \
        -O opencv.zip
    
    echo "Extracting..."
    unzip -q opencv.zip
    mv opencv-${OPENCV_VERSION} opencv
    rm opencv.zip
    echo -e "${GREEN}✓ OpenCV downloaded${NC}"
else
    echo -e "${GREEN}✓ OpenCV already exists${NC}"
fi

# Download opencv_contrib
if [ ! -d "opencv_contrib" ]; then
    echo "Downloading opencv_contrib..."
    wget -q --show-progress \
        https://github.com/opencv/opencv_contrib/archive/${OPENCV_VERSION}.zip \
        -O opencv_contrib.zip
    
    echo "Extracting..."
    unzip -q opencv_contrib.zip
    mv opencv_contrib-${OPENCV_VERSION} opencv_contrib
    rm opencv_contrib.zip
    echo -e "${GREEN}✓ OpenCV contrib downloaded${NC}"
else
    echo -e "${GREEN}✓ OpenCV contrib already exists${NC}"
fi

echo ""
echo "Current directory structure:"
ls -la
echo ""

# ============================================================================
# Step 4: Verify Directory Structure
# ============================================================================

echo -e "${BLUE}Step 4/7: Verifying Directory Structure${NC}"
echo ""

if [ ! -d "opencv" ]; then
    echo -e "${RED}✗ opencv directory not found!${NC}"
    exit 1
fi

if [ ! -d "opencv_contrib" ]; then
    echo -e "${RED}✗ opencv_contrib directory not found!${NC}"
    exit 1
fi

if [ ! -f "opencv/CMakeLists.txt" ]; then
    echo -e "${RED}✗ opencv/CMakeLists.txt not found!${NC}"
    exit 1
fi

if [ ! -d "opencv_contrib/modules" ]; then
    echo -e "${RED}✗ opencv_contrib/modules not found!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Directory structure verified${NC}"
echo "  - opencv: $(du -sh opencv | cut -f1)"
echo "  - opencv_contrib: $(du -sh opencv_contrib | cut -f1)"
echo ""

# ============================================================================
# Step 5: Create Build Directory
# ============================================================================

echo -e "${BLUE}Step 5/7: Creating Build Directory${NC}"
echo ""

cd opencv
mkdir -p build
cd build

echo "Current path: $(pwd)"
echo "Parent directory contents:"
ls -la ../ | head -10
echo ""

# Verify we can see opencv_contrib from here
CONTRIB_PATH="../../opencv_contrib/modules"
if [ -d "$CONTRIB_PATH" ]; then
    echo -e "${GREEN}✓ Can access contrib modules at: $CONTRIB_PATH${NC}"
    echo "  Modules found: $(ls $CONTRIB_PATH | wc -l)"
else
    echo -e "${RED}✗ Cannot access contrib modules at: $CONTRIB_PATH${NC}"
    exit 1
fi

echo ""

# ============================================================================
# Step 6: Configure with CMake
# ============================================================================

echo -e "${BLUE}Step 6/7: Configuring with CMake${NC}"
echo ""

echo -e "${YELLOW}This will take 5-10 minutes...${NC}"
echo ""

# Clean any previous cache
rm -rf *

# Run CMake
cmake \
    -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D WITH_GSTREAMER=ON \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="5.3,6.2,7.2,8.7" \
    -D WITH_CUBLAS=ON \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D WITH_V4L=ON \
    -D WITH_GTK=ON \
    -D WITH_FFMPEG=ON \
    -D OPENCV_EXTRA_MODULES_PATH=$CONTRIB_PATH \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    ..

CMAKE_RESULT=$?

echo ""
if [ $CMAKE_RESULT -ne 0 ]; then
    echo -e "${RED}✗ CMake configuration failed!${NC}"
    echo ""
    echo "Checking for error details..."
    if [ -f "CMakeFiles/CMakeError.log" ]; then
        echo "=== Last 20 lines of CMakeError.log ==="
        tail -20 CMakeFiles/CMakeError.log
    fi
    exit 1
fi

echo -e "${GREEN}✓ CMake configuration successful${NC}"
echo ""

# ============================================================================
# Step 7: Check GStreamer Detection
# ============================================================================

echo -e "${BLUE}Step 7/7: Checking GStreamer Detection${NC}"
echo ""

if [ -f "CMakeCache.txt" ]; then
    echo "GStreamer configuration:"
    grep -E "WITH_GSTREAMER|GSTREAMER_" CMakeCache.txt | grep -v "^//" | head -10
    echo ""
    
    if grep -q "WITH_GSTREAMER:BOOL=ON" CMakeCache.txt; then
        echo -e "${GREEN}✓ GStreamer: ENABLED${NC}"
        GSTREAMER_ENABLED=1
    else
        echo -e "${YELLOW}⚠ GStreamer: NOT ENABLED${NC}"
        GSTREAMER_ENABLED=0
    fi
else
    echo -e "${RED}✗ CMakeCache.txt not found${NC}"
    GSTREAMER_ENABLED=0
fi

echo ""

# ============================================================================
# Summary & Next Steps
# ============================================================================

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   CONFIGURATION SUMMARY                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "Build directory: $(pwd)"
echo "OpenCV version: $OPENCV_VERSION"
echo "GStreamer enabled: $([ $GSTREAMER_ENABLED -eq 1 ] && echo 'YES' || echo 'NO')"
echo ""

if [ $GSTREAMER_ENABLED -eq 1 ]; then
    echo -e "${GREEN}✓ Ready to build OpenCV with GStreamer support!${NC}"
    echo ""
    echo -e "${YELLOW}Next step:${NC}"
    echo ""
    echo "  make -j\$(nproc)"
    echo ""
    echo "This will take 30-90 minutes."
    echo ""
    echo "After build completes, install with:"
    echo "  sudo make install"
    echo "  sudo ldconfig"
else
    echo -e "${YELLOW}⚠ OpenCV configured but WITHOUT GStreamer${NC}"
    echo ""
    echo "You can either:"
    echo "1. Continue building anyway (use native GStreamer version later)"
    echo "2. Try to fix GStreamer detection and re-configure"
    echo ""
    echo "To build anyway:"
    echo "  make -j\$(nproc)"
fi

echo ""
echo -e "${BLUE}Current location: $(pwd)${NC}"
echo ""