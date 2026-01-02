#!/bin/bash
# Find available GStreamer packages on your system

echo "=========================================="
echo "Finding GStreamer Packages"
echo "=========================================="
echo ""

# Update package cache first
echo "Updating package cache..."
sudo apt-get update

echo ""
echo "Searching for available GStreamer packages..."
echo ""

# Search for GStreamer development packages
echo "1. GStreamer core development packages:"
echo "   ------------------------------------"
apt-cache search gstreamer | grep -E "^libgstreamer.*-dev" | head -10

echo ""
echo "2. GStreamer plugins base development packages:"
echo "   ----------------------------------------------"
apt-cache search gstreamer | grep -E "plugins-base.*-dev" | head -10

echo ""
echo "3. Checking specific package names:"
echo "   ---------------------------------"

check_pkg() {
    if apt-cache show "$1" &>/dev/null; then
        echo "   ✓ $1 (available)"
        return 0
    else
        echo "   ✗ $1 (not available)"
        return 1
    fi
}

# Try different package name variants
check_pkg "libgstreamer1.0-dev"
check_pkg "libgstreamer1.0-0"
check_pkg "libgstreamer-plugins-base1.0-dev"
check_pkg "gstreamer1.0-plugins-base"

echo ""
echo "4. Installed GStreamer packages:"
echo "   ------------------------------"
dpkg -l | grep gstreamer | grep "^ii" | awk '{print "   " $2}'

echo ""
echo "5. Available package versions:"
echo "   ---------------------------"
apt-cache policy libgstreamer1.0-dev 2>/dev/null || echo "   libgstreamer1.0-dev: Not found in repositories"

echo ""
echo "6. Repository sources:"
echo "   -------------------"
grep -h "^deb" /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null | grep -v "^#" | sort -u | head -10 | sed 's/^/   /'

echo ""
echo "=========================================="
echo "Recommended Action"
echo "=========================================="
echo ""

# Check if we can find any GStreamer dev packages
if apt-cache search gstreamer | grep -q "libgstreamer.*-dev"; then
    echo "GStreamer development packages ARE available in your repositories."
    echo ""
    echo "Try installing with these exact names:"
    echo ""
    apt-cache search gstreamer | grep -E "^libgstreamer.*-dev" | head -5 | awk '{print "  sudo apt-get install -y " $1}'
else
    echo "⚠️  WARNING: No GStreamer development packages found!"
    echo ""
    echo "This might mean:"
    echo "  1. Your repositories are not configured correctly"
    echo "  2. You need to enable the 'universe' repository"
    echo "  3. Your JetPack version uses different package names"
    echo ""
    echo "Possible fixes:"
    echo ""
    echo "Fix 1: Enable universe repository (for Ubuntu-based systems)"
    echo "  sudo add-apt-repository universe"
    echo "  sudo apt-get update"
    echo ""
    echo "Fix 2: Check your JetPack repositories"
    echo "  cat /etc/apt/sources.list.d/nvidia-l4t-apt-source.list"
    echo ""
    echo "Fix 3: Try installing from NVIDIA's repository"
    echo "  # For JetPack 4.x, GStreamer should be pre-installed"
    echo "  # Check if it's already there:"
    echo "  dpkg -l | grep gstreamer"
fi

echo ""
