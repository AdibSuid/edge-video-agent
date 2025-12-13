#!/bin/bash
# Install FFmpeg with NVENC/NVDEC support on Jetson
# This script installs a properly configured FFmpeg for hardware acceleration

set -e

echo "========================================="
echo "  FFmpeg NVENC/NVDEC Installation"
echo "  For Jetson Orin Nano Super"
echo "========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Error: This script is for Jetson platforms only"
    exit 1
fi

# Check JetPack version
echo "Checking JetPack version..."
if command -v jetson_release &> /dev/null; then
    jetson_release
else
    echo "jetson_release not found, checking manually..."
    dpkg -l | grep nvidia-jetpack || echo "JetPack info not available"
fi
echo ""

# Remove old FFmpeg if exists
echo "Removing old FFmpeg installation..."
sudo apt remove -y ffmpeg || true

# Install build dependencies
echo "Installing build dependencies..."
sudo apt update
sudo apt install -y \
    build-essential \
    pkg-config \
    yasm \
    cmake \
    libtool \
    libc6 \
    libc6-dev \
    unzip \
    wget \
    git \
    libx264-dev \
    libx265-dev \
    libnuma-dev

# Install FFmpeg from NVIDIA's multimedia API
echo ""
echo "Installing FFmpeg with L4T Multimedia API..."

# For JetPack 5.x, install ffmpeg with nvmpi
sudo apt install -y ffmpeg

# Add NVIDIA codec support via ffnvcodec
FFNVCODEC_VERSION="11.1.5.1"
FFMPEG_VERSION="5.1.3"

# Download and install ffnvcodec headers
echo ""
echo "Installing NVENC/NVDEC headers..."
cd /tmp
git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git || true
cd nv-codec-headers
git checkout n${FFNVCODEC_VERSION}
sudo make install

# Build FFmpeg with NVENC/NVDEC support
echo ""
echo "Building FFmpeg with NVENC/NVDEC support..."
echo "This will take 15-30 minutes..."
echo ""

cd /tmp
wget -q https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.bz2
tar xjf ffmpeg-${FFMPEG_VERSION}.tar.bz2
cd ffmpeg-${FFMPEG_VERSION}

./configure \
    --enable-nvenc \
    --enable-nvdec \
    --enable-cuvid \
    --enable-cuda \
    --enable-cuda-llvm \
    --enable-libnpp \
    --extra-cflags=-I/usr/local/cuda/include \
    --extra-ldflags=-L/usr/local/cuda/lib64 \
    --enable-gpl \
    --enable-libx264 \
    --enable-libx265 \
    --enable-nonfree \
    --disable-doc \
    --disable-htmlpages \
    --disable-manpages

make -j$(nproc)
sudo make install
sudo ldconfig

# Verify installation
echo ""
echo "========================================="
echo "  Verifying Installation"
echo "========================================="
echo ""

echo "FFmpeg version:"
ffmpeg -version | head -n 1
echo ""

echo "Checking for NVENC encoders:"
ffmpeg -encoders 2>/dev/null | grep nvenc || echo "⚠ NVENC not found"
echo ""

echo "Checking for NVDEC/CUVID decoders:"
ffmpeg -decoders 2>/dev/null | grep cuvid || echo "⚠ CUVID not found"
echo ""

# Test encoding
echo "Testing NVENC encoding..."
if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
    echo "✓ NVENC encoder available"
    
    # Create a test video
    ffmpeg -f lavfi -i testsrc=duration=1:size=1280x720:rate=30 -c:v h264_nvenc -preset p1 -y /tmp/test_nvenc.mp4 2>&1 | tail -n 5
    
    if [ -f /tmp/test_nvenc.mp4 ]; then
        echo "✓ NVENC encoding test successful"
        rm /tmp/test_nvenc.mp4
    else
        echo "✗ NVENC encoding test failed"
    fi
else
    echo "✗ NVENC encoder not available"
    echo ""
    echo "Alternative: Install FFmpeg from NVIDIA L4T multimedia API"
    echo "See: https://developer.nvidia.com/embedded/jetson-linux-archive"
fi

echo ""
echo "========================================="
echo "  Installation Complete"
echo "========================================="
echo ""
echo "To use FFmpeg with NVENC/NVDEC:"
echo "  Encoding: ffmpeg -i input.mp4 -c:v h264_nvenc -preset p1 output.mp4"
echo "  Decoding: ffmpeg -c:v h264_cuvid -i input.mp4 -c:v copy output.mp4"
echo ""
echo "Run hardware detection again:"
echo "  python3 detect_hardware.py"
echo ""

# Cleanup
rm -rf /tmp/ffmpeg-${FFMPEG_VERSION}*
rm -rf /tmp/nv-codec-headers
