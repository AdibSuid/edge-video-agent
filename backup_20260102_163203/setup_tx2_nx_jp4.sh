#!/bin/bash
# Setup script for Jetson TX2 NX with JetPack 4
# Installs required dependencies for hardware encode/decode

set -e

echo "========================================="
echo "Jetson TX2 NX JetPack 4 Setup"
echo "========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Error: Not running on a Jetson device"
    exit 1
fi

# Check JetPack version
echo "Detected Jetson platform:"
cat /etc/nv_tegra_release
echo ""

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install GStreamer and required plugins
echo ""
echo "Installing GStreamer and plugins..."
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-omx-generic \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Install FFmpeg (basic version with OMX support)
echo ""
echo "Installing FFmpeg..."
sudo apt-get install -y ffmpeg

# Check if OpenCV has GStreamer support
echo ""
echo "Checking OpenCV GStreamer support..."
python3 -c "
import cv2
import sys
build_info = cv2.getBuildInformation()
has_gstreamer = 'GStreamer' in build_info and 'YES' in build_info.split('GStreamer')[1].split('\n')[0]
print('OpenCV version:', cv2.__version__)
print('GStreamer support:', 'YES' if has_gstreamer else 'NO')

if not has_gstreamer:
    print('')
    print('WARNING: OpenCV does not have GStreamer support!')
    print('You need to rebuild OpenCV with GStreamer enabled.')
    print('See JETPACK4_TX2_SETUP.md for instructions.')
    sys.exit(1)
" || echo ""

# Add NVIDIA library path if not already present
echo ""
echo "Configuring NVIDIA library paths..."
if ! grep -q "tegra" ~/.bashrc; then
    echo 'export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/tegra:$LD_LIBRARY_PATH' >> ~/.bashrc
    echo "Added NVIDIA library path to ~/.bashrc"
fi

# Source the updated bashrc
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/tegra:$LD_LIBRARY_PATH

# Verify installations
echo ""
echo "========================================="
echo "Verification"
echo "========================================="

echo ""
echo "1. GStreamer version:"
gst-launch-1.0 --version | head -2

echo ""
echo "2. GStreamer OMX decoder (required for hardware decode):"
if gst-inspect-1.0 omxh264dec > /dev/null 2>&1; then
    echo "   ✓ omxh264dec available"
else
    echo "   ✗ omxh264dec NOT available"
fi

echo ""
echo "3. GStreamer OMX encoder:"
if gst-inspect-1.0 omxh264enc > /dev/null 2>&1; then
    echo "   ✓ omxh264enc available"
else
    echo "   ✗ omxh264enc NOT available"
fi

echo ""
echo "4. FFmpeg encoders:"
ffmpeg -encoders 2>/dev/null | grep -E "h264_nvenc|h264_omx|h264" | head -5

echo ""
echo "========================================="
echo "Next Steps"
echo "========================================="
echo ""
echo "1. Run diagnostic script:"
echo "   chmod +x check_jetpack4_hardware.sh"
echo "   ./check_jetpack4_hardware.sh"
echo ""
echo "2. Test hardware detection:"
echo "   python3 jetpack_utils.py"
echo ""
echo "3. If OpenCV lacks GStreamer support, you need to rebuild it."
echo "   See detailed instructions in: JETPACK4_TX2_SETUP.md"
echo ""
echo "4. Update your config.yaml:"
echo "   use_hardware_decode: true"
echo "   use_hardware_encode: true"
echo ""
echo "Setup complete!"
