#!/bin/bash
# Build OpenCV with GStreamer support for NVIDIA Jetson
# This script compiles OpenCV 4.8.0 with full GStreamer and CUDA support

set -e  # Exit on error

# Configuration
OPENCV_VERSION="4.8.0"
BUILD_DIR="$HOME/opencv_build"
INSTALL_PREFIX="/usr/local"
NUM_JOBS=$(nproc)  # Use all CPU cores

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Build OpenCV ${OPENCV_VERSION} with GStreamer for Jetson         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo -e "${RED}✗ Not running on NVIDIA Jetson${NC}"
    echo "This script is optimized for Jetson platforms"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}System Information:${NC}"
cat /etc/nv_tegra_release
echo ""
echo "CPU Cores: $NUM_JOBS"
echo "Build Directory: $BUILD_DIR"
echo "Install Prefix: $INSTALL_PREFIX"
echo ""

# Confirm before proceeding
echo -e "${YELLOW}This will:${NC}"
echo "  1. Install build dependencies (~500MB)"
echo "  2. Download OpenCV source (~200MB)"
echo "  3. Build OpenCV (takes 30-90 minutes)"
echo "  4. Install to $INSTALL_PREFIX"
echo ""
read -p "Proceed? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ============================================================================
# Step 1: Install Dependencies
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 1/6: Installing Dependencies${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

sudo apt-get update

echo -e "${GREEN}Installing build tools...${NC}"
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    wget \
    unzip

echo -e "${GREEN}Installing GStreamer and multimedia libraries...${NC}"
sudo apt-get install -y \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-tools \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3

echo -e "${GREEN}Installing image/video codecs...${NC}"
sudo apt-get install -y \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran

echo -e "${GREEN}Installing Python development headers...${NC}"
sudo apt-get install -y \
    python3-dev \
    python3-numpy \
    python3-pip

echo -e "${GREEN}✓ Dependencies installed${NC}"

# ============================================================================
# Step 2: Create Build Directory
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 2/6: Setting Up Build Directory${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ -d "$BUILD_DIR" ]; then
    echo -e "${YELLOW}Build directory exists. Remove it? (y/n)${NC}"
    read -p "> " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$BUILD_DIR"
    else
        echo "Using existing directory"
    fi
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo -e "${GREEN}✓ Build directory ready: $BUILD_DIR${NC}"

# ============================================================================
# Step 3: Download OpenCV Source
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 3/6: Downloading OpenCV ${OPENCV_VERSION}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -d "opencv" ]; then
    echo -e "${GREEN}Downloading opencv...${NC}"
    wget -O opencv.zip https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip
    unzip -q opencv.zip
    mv opencv-${OPENCV_VERSION} opencv
    rm opencv.zip
else
    echo "OpenCV source already downloaded"
fi

if [ ! -d "opencv_contrib" ]; then
    echo -e "${GREEN}Downloading opencv_contrib...${NC}"
    wget -O opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/${OPENCV_VERSION}.zip
    unzip -q opencv_contrib.zip
    mv opencv_contrib-${OPENCV_VERSION} opencv_contrib
    rm opencv_contrib.zip
else
    echo "OpenCV contrib already downloaded"
fi

echo -e "${GREEN}✓ OpenCV source downloaded${NC}"

# ============================================================================
# Step 4: Configure Build with CMake
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 4/6: Configuring Build with CMake${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd opencv
mkdir -p build
cd build

echo -e "${GREEN}Running CMake configuration...${NC}"
echo -e "${YELLOW}This may take 5-10 minutes...${NC}"

cmake \
    -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_INSTALL_PREFIX=$INSTALL_PREFIX \
    \
    `# GStreamer Support (CRITICAL)` \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    \
    `# CUDA Support (for Jetson)` \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="5.3,6.2,7.2,8.7" \
    -D CUDA_ARCH_PTX="" \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_CUBLAS=ON \
    \
    `# Python Support` \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D PYTHON3_INCLUDE_DIR=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())") \
    -D PYTHON3_PACKAGES_PATH=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())") \
    \
    `# Additional Features` \
    -D WITH_V4L=ON \
    -D WITH_LIBV4L=ON \
    -D WITH_GTK=ON \
    -D WITH_QT=OFF \
    -D WITH_OPENGL=ON \
    -D WITH_TBB=ON \
    \
    `# Video/Image Formats` \
    -D BUILD_JPEG=ON \
    -D BUILD_PNG=ON \
    -D BUILD_TIFF=ON \
    -D WITH_FFMPEG=ON \
    \
    `# Contrib Modules` \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
    \
    `# Build Options` \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_DOCS=OFF \
    \
    `# Installation` \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    ..

# Check if CMake succeeded
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CMake configuration successful${NC}"
else
    echo -e "${RED}✗ CMake configuration failed${NC}"
    exit 1
fi

# Verify GStreamer is enabled
echo ""
echo -e "${YELLOW}Checking GStreamer configuration...${NC}"
if grep -q "GStreamer.*YES" CMakeCache.txt; then
    echo -e "${GREEN}✓ GStreamer support: ENABLED${NC}"
else
    echo -e "${RED}✗ GStreamer support: DISABLED${NC}"
    echo -e "${YELLOW}This is a problem! Check CMake output above for errors.${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ============================================================================
# Step 5: Build OpenCV
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 5/6: Building OpenCV${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}Building with $NUM_JOBS parallel jobs...${NC}"
echo -e "${YELLOW}This will take 30-90 minutes depending on your Jetson model${NC}"
echo ""
echo "You can monitor progress with: watch -n 5 'ps aux | grep make'"
echo ""

# Free up memory before building
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# Build
START_TIME=$(date +%s)

if make -j${NUM_JOBS}; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))
    
    echo ""
    echo -e "${GREEN}✓ Build completed successfully in ${MINUTES}m ${SECONDS}s${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    echo ""
    echo "Common issues:"
    echo "  1. Out of memory - try with fewer jobs: make -j2"
    echo "  2. Missing dependencies - check Step 1 output"
    echo "  3. Compilation error - check error messages above"
    exit 1
fi

# ============================================================================
# Step 6: Install OpenCV
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 6/6: Installing OpenCV${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${GREEN}Installing to $INSTALL_PREFIX...${NC}"
sudo make install
sudo ldconfig

echo -e "${GREEN}✓ Installation complete${NC}"

# ============================================================================
# Verification
# ============================================================================

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo -e "${YELLOW}Testing Python OpenCV import...${NC}"
python3 -c "import cv2; print(f'OpenCV Version: {cv2.__version__}')" || {
    echo -e "${RED}✗ Failed to import cv2${NC}"
    exit 1
}

echo ""
echo -e "${YELLOW}Checking GStreamer support...${NC}"
python3 << 'EOF'
import cv2

info = cv2.getBuildInformation()

# Check for GStreamer
if 'GStreamer' in info:
    lines = info.split('\n')
    for i, line in enumerate(lines):
        if 'GStreamer' in line:
            # Print GStreamer section
            print(lines[i])
            if i+1 < len(lines):
                print(lines[i+1])
            
            if 'YES' in line or 'YES' in lines[i+1]:
                print('\n✓ GStreamer support: ENABLED')
                exit(0)
            else:
                print('\n✗ GStreamer support: DISABLED')
                exit(1)
else:
    print('✗ GStreamer not found in build info')
    exit(1)
EOF

GSTREAMER_CHECK=$?

echo ""
echo -e "${YELLOW}Checking CUDA support...${NC}"
python3 -c "import cv2; print('✓ CUDA support:', 'ENABLED' if cv2.cuda.getCudaEnabledDeviceCount() > 0 else 'DISABLED')" || {
    echo "CUDA check inconclusive"
}

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    BUILD SUMMARY                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

python3 << 'EOF'
import cv2
print(f"OpenCV Version: {cv2.__version__}")
print(f"Install Path: {cv2.__file__}")
print(f"Build Info: {cv2.getBuildInformation().split('\\n')[0]}")
EOF

echo ""
if [ $GSTREAMER_CHECK -eq 0 ]; then
    echo -e "${GREEN}✓ GStreamer Support: ENABLED${NC}"
    echo ""
    echo "You can now use OpenCV with GStreamer!"
    echo ""
    echo "Next steps:"
    echo "  1. Use the original streamer_jetson_hw.py (OpenCV version)"
    echo "  2. cp streamer_jetson_hw.py streamer.py"
    echo "  3. python app.py"
else
    echo -e "${RED}✗ GStreamer Support: NOT ENABLED${NC}"
    echo ""
    echo "Something went wrong. Check the build configuration."
    echo "You may need to:"
    echo "  1. Install missing GStreamer packages"
    echo "  2. Re-run CMake with verbose output: cmake .. 2>&1 | tee cmake.log"
    echo "  3. Check cmake.log for GStreamer detection issues"
fi

echo ""
echo -e "${YELLOW}Build artifacts located at: $BUILD_DIR${NC}"
echo -e "${YELLOW}You can remove this directory to free space: rm -rf $BUILD_DIR${NC}"
echo ""

echo -e "${GREEN}Build script completed!${NC}"