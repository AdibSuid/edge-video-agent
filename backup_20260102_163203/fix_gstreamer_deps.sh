#!/bin/bash
# Quick fix script for GStreamer dependencies
# Run this if diagnose_gstreamer.sh reports missing packages

echo "=========================================="
echo "GStreamer Dependencies Fix Script"
echo "=========================================="
echo ""

# Update package list
echo "Updating package list..."
sudo apt-get update

echo ""
echo "Installing GStreamer packages in correct order..."
echo ""

# Step 1: Install pkg-config first (critical)
echo "Step 1: Installing pkg-config..."
sudo apt-get install -y pkg-config

# Step 2: Install GStreamer base library
echo ""
echo "Step 2: Installing GStreamer base library..."
sudo apt-get install -y libgstreamer1.0-0 libgstreamer1.0-dev

# Step 3: Install GStreamer plugins base
echo ""
echo "Step 3: Installing GStreamer plugins base..."
sudo apt-get install -y \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-base-apps

# Step 4: Install additional plugins
echo ""
echo "Step 4: Installing additional GStreamer plugins..."
sudo apt-get install -y \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools

# Step 5: Verify installation
echo ""
echo "=========================================="
echo "Verification"
echo "=========================================="
echo ""

SUCCESS=1

# Check pkg-config
if command -v pkg-config &> /dev/null; then
    echo "✓ pkg-config installed"
else
    echo "✗ pkg-config NOT installed"
    SUCCESS=0
fi

# Check if pkg-config can find GStreamer
if pkg-config --exists gstreamer-1.0; then
    VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo "✓ gstreamer-1.0 found (version $VERSION)"
else
    echo "✗ gstreamer-1.0 NOT found via pkg-config"
    SUCCESS=0
fi

if pkg-config --exists gstreamer-base-1.0; then
    echo "✓ gstreamer-base-1.0 found"
else
    echo "✗ gstreamer-base-1.0 NOT found"
    SUCCESS=0
fi

if pkg-config --exists gstreamer-video-1.0; then
    echo "✓ gstreamer-video-1.0 found"
else
    echo "✗ gstreamer-video-1.0 NOT found"
    SUCCESS=0
fi

# Check for header files
if [ -f "/usr/include/gstreamer-1.0/gst/gst.h" ]; then
    echo "✓ GStreamer header files found"
else
    echo "✗ GStreamer header files NOT found"
    SUCCESS=0
fi

echo ""

if [ $SUCCESS -eq 1 ]; then
    echo "=========================================="
    echo "✓ SUCCESS!"
    echo "=========================================="
    echo ""
    echo "All GStreamer dependencies are now installed."
    echo ""
    echo "Next steps:"
    echo "  1. If you were building OpenCV, clean the build directory:"
    echo "     rm -rf ~/opencv_build/opencv-*/build/*"
    echo ""
    echo "  2. Re-run the OpenCV build script:"
    echo "     ./rebuild_opencv_tx2.sh"
else
    echo "=========================================="
    echo "✗ SOME ISSUES REMAIN"
    echo "=========================================="
    echo ""
    echo "Please run the diagnostic script for more details:"
    echo "  ./diagnose_gstreamer.sh"
    echo ""
    echo "You may also need to:"
    echo "  1. Check your internet connection"
    echo "  2. Try: sudo apt-get update && sudo apt-get upgrade"
    echo "  3. Check JetPack version compatibility"
fi

echo ""
