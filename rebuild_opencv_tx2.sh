#!/bin/bash
# Automated OpenCV rebuild script for TX2 NX with GStreamer support
# Run this on your TX2 NX with JetPack 4.5.1

set -e  # Exit on error

OPENCV_VERSION="4.5.5"
WORKSPACE="$HOME/opencv_build"

echo "=========================================="
echo "OpenCV ${OPENCV_VERSION} Build Script"
echo "for Jetson TX2 NX + JetPack 4.5.1"
echo "=========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "ERROR: This script must be run on a Jetson device"
    exit 1
fi

echo "Detected Jetson platform:"
cat /etc/nv_tegra_release
echo ""

# Check available disk space
AVAILABLE_SPACE=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 5 ]; then
    echo "WARNING: Less than 5GB free space available"
    echo "Available: ${AVAILABLE_SPACE}GB"
    echo "Recommended: At least 5GB"
    echo ""
    read -p "Continue anyway? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Step 1: Installing dependencies..."
echo "-----------------------------------"
sudo apt-get update

# Install GStreamer
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Install build dependencies
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
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
    gfortran \
    python3-dev \
    python3-numpy \
    libtbb2 \
    libtbb-dev \
    libdc1394-22-dev

echo ""
echo "Step 2: Removing old OpenCV installations..."
echo "---------------------------------------------"
# Remove pip installations
pip3 uninstall -y opencv-python opencv-contrib-python opencv-python-headless 2>/dev/null || true

echo ""
echo "Step 3: Downloading OpenCV ${OPENCV_VERSION}..."
echo "------------------------------------------------"

# Create workspace
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# Download OpenCV if not already present
if [ ! -d "opencv-${OPENCV_VERSION}" ]; then
    echo "Downloading OpenCV..."
    wget -O opencv.zip "https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip"
    unzip opencv.zip
    rm opencv.zip
else
    echo "OpenCV source already downloaded"
fi

if [ ! -d "opencv_contrib-${OPENCV_VERSION}" ]; then
    echo "Downloading OpenCV contrib..."
    wget -O opencv_contrib.zip "https://github.com/opencv/opencv_contrib/archive/${OPENCV_VERSION}.zip"
    unzip opencv_contrib.zip
    rm opencv_contrib.zip
else
    echo "OpenCV contrib already downloaded"
fi

echo ""
echo "Step 4: Configuring CMake..."
echo "----------------------------"

cd "opencv-${OPENCV_VERSION}"
rm -rf build
mkdir build
cd build

# Get Python 3 paths
PYTHON3_EXEC=$(which python3)
PYTHON3_INCLUDE=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())")
PYTHON3_PACKAGES=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

echo "Python configuration:"
echo "  Executable: $PYTHON3_EXEC"
echo "  Include: $PYTHON3_INCLUDE"
echo "  Packages: $PYTHON3_PACKAGES"
echo ""

# Configure with GStreamer and CUDA support
cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D OPENCV_EXTRA_MODULES_PATH="../../opencv_contrib-${OPENCV_VERSION}/modules" \
    -D EIGEN_INCLUDE_PATH=/usr/include/eigen3 \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="6.2" \
    -D CUDA_ARCH_PTX="" \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_CUBLAS=ON \
    -D WITH_LIBV4L=ON \
    -D WITH_V4L=ON \
    -D BUILD_opencv_python3=ON \
    -D BUILD_opencv_python2=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_EXAMPLES=OFF \
    -D WITH_QT=OFF \
    -D WITH_GTK=ON \
    -D WITH_OPENGL=ON \
    -D WITH_TBB=ON \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    -D PYTHON3_EXECUTABLE="$PYTHON3_EXEC" \
    -D PYTHON3_INCLUDE_DIR="$PYTHON3_INCLUDE" \
    -D PYTHON3_PACKAGES_PATH="$PYTHON3_PACKAGES" \
    ..

echo ""
echo "=========================================="
echo "IMPORTANT: Verify CMake Configuration"
echo "=========================================="
echo ""
echo "Check the output above for:"
echo "  ✓ GStreamer: YES (1.14.x)"
echo "  ✓ NVIDIA CUDA: YES (10.2)"
echo "  ✓ Python 3: Correct paths"
echo ""

# Check if GStreamer was found
if grep -q "GStreamer:.*YES" CMakeCache.txt; then
    echo "✓ GStreamer support: ENABLED"
else
    echo "✗ GStreamer support: DISABLED"
    echo ""
    echo "ERROR: GStreamer was not enabled!"
    echo "Please check the errors above and fix dependencies."
    exit 1
fi

echo ""
read -p "Configuration looks good? Press Enter to start build (or Ctrl+C to abort)..."

echo ""
echo "Step 5: Building OpenCV (this will take ~2 hours)..."
echo "-----------------------------------------------------"
echo "Started at: $(date)"
echo ""

# Build with all 4 cores
# If you run into memory issues, change -j4 to -j2
make -j4

echo ""
echo "Build completed at: $(date)"
echo ""

echo "Step 6: Installing OpenCV..."
echo "-----------------------------"
sudo make install
sudo ldconfig

echo ""
echo "Step 7: Verifying installation..."
echo "----------------------------------"

# Test import
python3 -c "import cv2; print('OpenCV version:', cv2.__version__)" || {
    echo "ERROR: Could not import OpenCV"
    exit 1
}

# Check GStreamer support
python3 -c "
import cv2
import sys
info = cv2.getBuildInformation()
has_gs = 'GStreamer' in info and 'YES' in info.split('GStreamer')[1].split('\n')[0]
print('GStreamer support:', 'YES ✓' if has_gs else 'NO ✗')
if not has_gs:
    print('')
    print('ERROR: OpenCV built without GStreamer support!')
    sys.exit(1)
" || {
    echo "Build succeeded but GStreamer support is missing!"
    exit 1
}

echo ""
echo "=========================================="
echo "✓ SUCCESS!"
echo "=========================================="
echo ""
echo "OpenCV ${OPENCV_VERSION} has been installed with:"
echo "  ✓ GStreamer support"
echo "  ✓ CUDA support"
echo "  ✓ Python 3 bindings"
echo ""
echo "Next steps:"
echo "  1. Update your code to use GStreamer encoding"
echo "  2. See: STEP_BY_STEP_FIX.md (Step 6)"
echo "  3. Test with: ./test_tx2_compatibility.sh"
echo ""
echo "Build artifacts saved in: $WORKSPACE"
echo "You can delete this folder to save space after verifying everything works."
echo ""
