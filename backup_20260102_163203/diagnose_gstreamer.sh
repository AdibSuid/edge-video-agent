#!/bin/bash
# Diagnostic script to check GStreamer installation for OpenCV build

echo "=========================================="
echo "GStreamer Installation Diagnostics"
echo "=========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "WARNING: Not running on a Jetson device"
    echo "This script is designed for Jetson platforms"
    echo ""
fi

# 1. Check if GStreamer runtime is installed
echo "1. GStreamer Runtime:"
echo "   ------------------"
if command -v gst-launch-1.0 &> /dev/null; then
    echo "   ✓ gst-launch-1.0 found"
    gst-launch-1.0 --version | head -2 | sed 's/^/   /'
else
    echo "   ✗ gst-launch-1.0 NOT found"
    echo "   Install: sudo apt-get install gstreamer1.0-tools"
fi
echo ""

# 2. Check for GStreamer development libraries
echo "2. GStreamer Development Libraries:"
echo "   ---------------------------------"

check_package() {
    if dpkg -l | grep -q "^ii.*$1"; then
        echo "   ✓ $1"
        return 0
    else
        echo "   ✗ $1 (NOT INSTALLED)"
        return 1
    fi
}

MISSING=0

check_package "libgstreamer1.0-dev" || MISSING=1
check_package "libgstreamer-plugins-base1.0-dev" || MISSING=1
check_package "gstreamer1.0-plugins-base" || MISSING=1
check_package "gstreamer1.0-plugins-good" || MISSING=1
check_package "gstreamer1.0-plugins-bad" || MISSING=1

echo ""

# 3. Check pkg-config
echo "3. pkg-config Configuration:"
echo "   --------------------------"
if command -v pkg-config &> /dev/null; then
    echo "   ✓ pkg-config installed"

    if pkg-config --exists gstreamer-1.0; then
        echo "   ✓ gstreamer-1.0 found via pkg-config"
        VERSION=$(pkg-config --modversion gstreamer-1.0)
        echo "     Version: $VERSION"
        CFLAGS=$(pkg-config --cflags gstreamer-1.0 2>&1 | head -c 100)
        echo "     CFLAGS: $CFLAGS..."
    else
        echo "   ✗ gstreamer-1.0 NOT found via pkg-config"
        echo "     This is the MAIN ISSUE!"
        MISSING=1
    fi

    echo ""

    if pkg-config --exists gstreamer-base-1.0; then
        echo "   ✓ gstreamer-base-1.0 found via pkg-config"
    else
        echo "   ✗ gstreamer-base-1.0 NOT found via pkg-config"
        MISSING=1
    fi

    if pkg-config --exists gstreamer-video-1.0; then
        echo "   ✓ gstreamer-video-1.0 found via pkg-config"
    else
        echo "   ✗ gstreamer-video-1.0 NOT found via pkg-config"
        MISSING=1
    fi
else
    echo "   ✗ pkg-config NOT installed"
    echo "   Install: sudo apt-get install pkg-config"
    MISSING=1
fi

echo ""

# 4. Check for GStreamer header files
echo "4. GStreamer Header Files:"
echo "   -----------------------"

check_header() {
    if [ -f "$1" ]; then
        echo "   ✓ $1"
        return 0
    else
        echo "   ✗ $1 (NOT FOUND)"
        return 1
    fi
}

check_header "/usr/include/gstreamer-1.0/gst/gst.h" || MISSING=1
check_header "/usr/include/gstreamer-1.0/gst/gstversion.h" || MISSING=1

# Check if gstreamer-1.0 directory exists
if [ -d "/usr/include/gstreamer-1.0" ]; then
    echo "   ✓ /usr/include/gstreamer-1.0 directory exists"
else
    echo "   ✗ /usr/include/gstreamer-1.0 directory NOT found"
    MISSING=1
fi

echo ""

# 5. Check PKG_CONFIG_PATH environment variable
echo "5. Environment Variables:"
echo "   ----------------------"
if [ -z "$PKG_CONFIG_PATH" ]; then
    echo "   ⚠ PKG_CONFIG_PATH is not set (usually OK)"
else
    echo "   PKG_CONFIG_PATH=$PKG_CONFIG_PATH"
fi

# Check standard pkg-config paths
echo ""
echo "   Standard pkg-config search paths:"
pkg-config --variable pc_path pkg-config | tr ':' '\n' | sed 's/^/     /'

echo ""

# 6. Summary and recommendations
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""

if [ $MISSING -eq 0 ]; then
    echo "✓ All GStreamer dependencies appear to be installed correctly"
    echo ""
    echo "If OpenCV CMake still fails to find GStreamer, try:"
    echo "  1. Clean the build directory: rm -rf ~/opencv_build/opencv-*/build/*"
    echo "  2. Re-run CMake"
    echo "  3. Check CMake output for specific error messages"
else
    echo "✗ Missing GStreamer dependencies detected"
    echo ""
    echo "To fix, run these commands:"
    echo ""
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y \\"
    echo "      pkg-config \\"
    echo "      libgstreamer1.0-dev \\"
    echo "      libgstreamer-plugins-base1.0-dev \\"
    echo "      gstreamer1.0-plugins-base \\"
    echo "      gstreamer1.0-plugins-good \\"
    echo "      gstreamer1.0-plugins-bad \\"
    echo "      gstreamer1.0-plugins-ugly \\"
    echo "      gstreamer1.0-libav \\"
    echo "      gstreamer1.0-tools"
    echo ""
    echo "Then re-run the OpenCV build script."
fi

echo ""
echo "=========================================="
echo "Additional Diagnostics"
echo "=========================================="
echo ""

# Check if we can compile a simple GStreamer program
echo "Testing if GStreamer can be compiled..."
cat > /tmp/test_gst.c << 'CEOF'
#include <gst/gst.h>
int main(int argc, char *argv[]) {
    gst_init(&argc, &argv);
    return 0;
}
CEOF

if gcc /tmp/test_gst.c -o /tmp/test_gst $(pkg-config --cflags --libs gstreamer-1.0) 2>/dev/null; then
    echo "✓ Successfully compiled test GStreamer program"
    rm -f /tmp/test_gst /tmp/test_gst.c
else
    echo "✗ Failed to compile test GStreamer program"
    echo ""
    echo "Compilation error:"
    gcc /tmp/test_gst.c -o /tmp/test_gst $(pkg-config --cflags --libs gstreamer-1.0) 2>&1 | head -10 | sed 's/^/  /'
    rm -f /tmp/test_gst.c
fi

echo ""
echo "Diagnostics complete!"
