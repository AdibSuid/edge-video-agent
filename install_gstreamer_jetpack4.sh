#!/bin/bash
# GStreamer installation script specifically for JetPack 4.x
# Works around package availability issues

set -e

echo "=========================================="
echo "GStreamer Installation for JetPack 4.x"
echo "=========================================="
echo ""

# Check if on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "WARNING: Not running on a Jetson device"
    echo ""
fi

echo "System information:"
if [ -f /etc/nv_tegra_release ]; then
    cat /etc/nv_tegra_release
fi
echo ""

# Function to try installing a package
try_install() {
    local package=$1
    echo "Trying to install: $package"
    if sudo apt-get install -y "$package" 2>/dev/null; then
        echo "  ✓ Installed: $package"
        return 0
    else
        echo "  ✗ Failed: $package (not available)"
        return 1
    fi
}

# Update package list
echo "Updating package list..."
sudo apt-get update

echo ""
echo "Step 1: Installing pkg-config (required)"
echo "-----------------------------------------"
sudo apt-get install -y pkg-config

echo ""
echo "Step 2: Checking what's already installed"
echo "------------------------------------------"
echo "Currently installed GStreamer packages:"
dpkg -l | grep gstreamer | grep "^ii" | awk '{print "  " $2}' || echo "  None found"

echo ""
echo "Step 3: Installing GStreamer packages"
echo "--------------------------------------"

# Array of packages to try (in order of preference)
declare -a CORE_PACKAGES=(
    "libgstreamer1.0-dev"
    "libgstreamer1.0-0"
    "gstreamer1.0-tools"
)

declare -a BASE_PACKAGES=(
    "libgstreamer-plugins-base1.0-dev"
    "gstreamer1.0-plugins-base"
    "gstreamer1.0-plugins-base-apps"
)

declare -a PLUGIN_PACKAGES=(
    "gstreamer1.0-plugins-good"
    "gstreamer1.0-plugins-bad"
    "gstreamer1.0-plugins-ugly"
    "gstreamer1.0-libav"
)

echo ""
echo "Installing core GStreamer..."
CORE_INSTALLED=0
for pkg in "${CORE_PACKAGES[@]}"; do
    if try_install "$pkg"; then
        CORE_INSTALLED=1
    fi
done

echo ""
echo "Installing GStreamer plugins base..."
BASE_INSTALLED=0
for pkg in "${BASE_PACKAGES[@]}"; do
    if try_install "$pkg"; then
        BASE_INSTALLED=1
    fi
done

echo ""
echo "Installing additional plugins..."
for pkg in "${PLUGIN_PACKAGES[@]}"; do
    try_install "$pkg" || true  # Don't fail if plugins not available
done

echo ""
echo "=========================================="
echo "Verification"
echo "=========================================="
echo ""

# Check what was installed
echo "Installed packages:"
dpkg -l | grep gstreamer | grep "^ii" | awk '{print "  " $2}'

echo ""

# Check if pkg-config can find GStreamer
echo "Checking pkg-config detection:"
if pkg-config --exists gstreamer-1.0 2>/dev/null; then
    VERSION=$(pkg-config --modversion gstreamer-1.0)
    echo "  ✓ gstreamer-1.0 found (version $VERSION)"

    # Show what pkg-config found
    echo ""
    echo "GStreamer configuration from pkg-config:"
    pkg-config --cflags gstreamer-1.0 | sed 's/^/    CFLAGS: /'
    pkg-config --libs gstreamer-1.0 | sed 's/^/    LIBS: /'
else
    echo "  ✗ gstreamer-1.0 NOT found via pkg-config"
    echo ""
    echo "This is a problem. Checking why..."
    echo ""

    # Debug: find .pc files
    echo "Looking for gstreamer .pc files:"
    find /usr -name "gstreamer*.pc" 2>/dev/null | sed 's/^/  /' || echo "  None found"

    echo ""
    echo "pkg-config search paths:"
    pkg-config --variable pc_path pkg-config | tr ':' '\n' | sed 's/^/  /'
fi

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""

if pkg-config --exists gstreamer-1.0 2>/dev/null; then
    echo "✓ GStreamer is installed and detectable"
    echo ""
    echo "You can now:"
    echo "  1. Clean previous OpenCV build: rm -rf ~/opencv_build/opencv-*/build/*"
    echo "  2. Re-run OpenCV build: ./rebuild_opencv_tx2.sh"
else
    echo "⚠️  GStreamer packages are installed but pkg-config can't find them"
    echo ""
    echo "Possible causes:"
    echo "  1. Package names are different on your JetPack version"
    echo "  2. .pc files are in non-standard location"
    echo "  3. Development packages are not available in your repositories"
    echo ""
    echo "Alternative solutions:"
    echo ""
    echo "Option A: Use pre-installed GStreamer (JetPack usually includes it)"
    echo "  # Check if GStreamer is already usable:"
    echo "  gst-launch-1.0 --version"
    echo "  # If yes, you may need to build OpenCV differently"
    echo ""
    echo "Option B: Manual pkg-config path setup"
    echo "  # Find where .pc files are:"
    echo "  find /usr -name 'gstreamer-1.0.pc'"
    echo "  # If found in /usr/lib/aarch64-linux-gnu/pkgconfig, add to path:"
    echo "  export PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig:\$PKG_CONFIG_PATH"
    echo ""
    echo "Option C: Skip OpenCV rebuild (use existing GStreamer in code)"
    echo "  # Your code already uses GStreamer for encoding"
    echo "  # You only need nvv4l2h264enc which is in gstreamer1.0-plugins"
    echo "  # You might not need OpenCV with GStreamer for decode"
    echo ""
    echo "Run ./find_gstreamer_packages.sh for detailed diagnostics"
fi

echo ""
