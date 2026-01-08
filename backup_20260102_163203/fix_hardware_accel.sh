#!/bin/bash
# Quick fix for common hardware acceleration issues on Jetson

echo "=========================================="
echo "Jetson Hardware Acceleration Quick Fix"
echo "=========================================="
echo ""

# Check if on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "ERROR: Not running on a Jetson device"
    exit 1
fi

echo "Step 1: Installing GStreamer plugins"
echo "-------------------------------------"

# Install GStreamer bad plugins (contains nvv4l2 encoders/decoders)
echo "Installing gstreamer1.0-plugins-bad (contains nvv4l2 plugins)..."
sudo apt-get update
sudo apt-get install -y gstreamer1.0-plugins-bad

echo ""
echo "Installing additional GStreamer packages..."
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

echo ""
echo "Step 2: Fixing permissions"
echo "--------------------------"

# Add user to video group
if ! groups $USER | grep -q video; then
    echo "Adding $USER to 'video' group..."
    sudo usermod -a -G video $USER
    echo "✓ Added to video group"
    echo "⚠️  You MUST logout and login for this to take effect!"
    echo ""
    NEED_RELOGIN=1
else
    echo "✓ User already in 'video' group"
    NEED_RELOGIN=0
fi

echo ""
echo "Step 3: Verifying installation"
echo "-------------------------------"

# Check if plugins are now available
echo "Checking for nvv4l2 plugins..."
if gst-inspect-1.0 nvv4l2decoder &> /dev/null; then
    echo "  ✓ nvv4l2decoder found"
else
    echo "  ✗ nvv4l2decoder NOT found"
fi

if gst-inspect-1.0 nvv4l2h264enc &> /dev/null; then
    echo "  ✓ nvv4l2h264enc found"
else
    echo "  ✗ nvv4l2h264enc NOT found"
fi

echo ""
echo "Step 4: Testing hardware"
echo "------------------------"

# Quick test
echo "Running quick hardware test..."
if timeout 3 gst-launch-1.0 videotestsrc num-buffers=10 ! nvv4l2h264enc ! fakesink &> /dev/null; then
    echo "  ✓ Hardware encoder test PASSED"
else
    echo "  ✗ Hardware encoder test FAILED"
    echo ""
    echo "  Debugging:"
    gst-launch-1.0 videotestsrc num-buffers=10 ! nvv4l2h264enc ! fakesink 2>&1 | grep -i error | sed 's/^/    /'
fi

echo ""
echo "=========================================="
echo "RESULTS"
echo "=========================================="
echo ""

if [ $NEED_RELOGIN -eq 1 ]; then
    echo "⚠️  IMPORTANT: You MUST logout and login again!"
    echo ""
    echo "The video group membership won't take effect until you do."
    echo ""
    echo "After logging back in:"
    echo "  1. Run: ./test_hardware_acceleration.sh"
    echo "  2. All tests should pass"
    echo "  3. Run your application: python3 app.py"
else
    echo "✓ Fixes applied"
    echo ""
    echo "Next steps:"
    echo "  1. Run comprehensive test: ./test_hardware_acceleration.sh"
    echo "  2. If tests pass, run: python3 app.py"
    echo "  3. Check logs for any remaining errors"
fi

echo ""
