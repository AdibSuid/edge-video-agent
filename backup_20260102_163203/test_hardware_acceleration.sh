#!/bin/bash
# Comprehensive hardware acceleration test for Jetson TX2 NX

echo "=========================================="
echo "Jetson Hardware Acceleration Diagnostic"
echo "=========================================="
echo ""

# Check if on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "ERROR: Not running on a Jetson device"
    exit 1
fi

echo "System Information:"
cat /etc/nv_tegra_release
echo ""

# 1. Check GStreamer installation
echo "1. GStreamer Installation:"
echo "   -----------------------"
if command -v gst-inspect-1.0 &> /dev/null; then
    echo "   ✓ gst-inspect-1.0 found"
    gst-launch-1.0 --version | head -2 | sed 's/^/   /'
else
    echo "   ✗ gst-inspect-1.0 NOT found"
    echo "   Install: sudo apt-get install gstreamer1.0-tools"
fi

echo ""

# 2. Check for NVIDIA video acceleration plugins
echo "2. NVIDIA Hardware Acceleration Plugins:"
echo "   --------------------------------------"

check_plugin() {
    local plugin=$1
    local description=$2

    if gst-inspect-1.0 "$plugin" &> /dev/null; then
        echo "   ✓ $plugin - $description"
        return 0
    else
        echo "   ✗ $plugin - $description (NOT FOUND)"
        return 1
    fi
}

DECODER_OK=0
ENCODER_OK=0

check_plugin "nvv4l2decoder" "Hardware video decoder" && DECODER_OK=1
check_plugin "nvv4l2h264enc" "Hardware H.264 encoder" && ENCODER_OK=1
check_plugin "nvvidconv" "NVIDIA video converter" || echo "   ⚠ Missing nvvidconv (needed for color conversion)"

echo ""

# 3. Check device permissions
echo "3. Video Hardware Device Permissions:"
echo "   -----------------------------------"

check_device() {
    local device=$1
    if [ -c "$device" ]; then
        PERMS=$(ls -l "$device" | awk '{print $1, $3, $4}')
        echo "   ✓ $device exists: $PERMS"

        # Check if current user can access
        if [ -r "$device" ] && [ -w "$device" ]; then
            echo "     ✓ Current user CAN access"
        else
            echo "     ✗ Current user CANNOT access (permission issue)"
            echo "     Fix: sudo usermod -a -G video $USER"
            echo "          Then logout and login again"
        fi
        return 0
    else
        echo "   ✗ $device does NOT exist"
        return 1
    fi
}

check_device "/dev/nvhost-ctrl"
check_device "/dev/nvhost-nvdec"
check_device "/dev/nvhost-nvenc"
check_device "/dev/nvhost-vic"

echo ""

# 4. Check user groups
echo "4. User Group Membership:"
echo "   ----------------------"
echo "   Current user: $USER"
echo "   Groups: $(groups)"

if groups | grep -q video; then
    echo "   ✓ User is in 'video' group"
else
    echo "   ✗ User is NOT in 'video' group"
    echo "   Fix: sudo usermod -a -G video $USER"
    echo "        Then logout and login"
fi

echo ""

# 5. Test hardware decoder
echo "5. Testing Hardware Decoder (nvv4l2decoder):"
echo "   ------------------------------------------"

if [ $DECODER_OK -eq 1 ]; then
    echo "   Running test pipeline..."

    DECODE_TEST=$(timeout 5 gst-launch-1.0 -e \
        videotestsrc num-buffers=30 ! \
        'video/x-raw,width=1920,height=1080,framerate=30/1' ! \
        x264enc ! h264parse ! nvv4l2decoder ! fakesink 2>&1)

    if [ $? -eq 0 ]; then
        echo "   ✓ Hardware decoder TEST PASSED"
    else
        echo "   ✗ Hardware decoder TEST FAILED"
        echo ""
        echo "   Error output:"
        echo "$DECODE_TEST" | grep -i "error\|failed\|could not" | sed 's/^/     /'
        echo ""
        echo "   Common causes:"
        echo "     - Permission denied on /dev/nvhost-nvdec"
        echo "     - Missing firmware or driver"
        echo "     - Incompatible video format"
    fi
else
    echo "   ✗ SKIPPED - nvv4l2decoder plugin not found"
fi

echo ""

# 6. Test hardware encoder
echo "6. Testing Hardware Encoder (nvv4l2h264enc):"
echo "   ------------------------------------------"

if [ $ENCODER_OK -eq 1 ]; then
    echo "   Running test pipeline..."

    ENCODE_OUTPUT="/tmp/test_encode_$$.mp4"
    ENCODE_TEST=$(timeout 5 gst-launch-1.0 -e \
        videotestsrc num-buffers=30 ! \
        'video/x-raw,width=1920,height=1080,framerate=30/1' ! \
        nvv4l2h264enc bitrate=2000000 ! \
        h264parse ! qtmux ! filesink location="$ENCODE_OUTPUT" 2>&1)

    if [ $? -eq 0 ] && [ -f "$ENCODE_OUTPUT" ]; then
        FILE_SIZE=$(stat -f%z "$ENCODE_OUTPUT" 2>/dev/null || stat -c%s "$ENCODE_OUTPUT" 2>/dev/null)
        echo "   ✓ Hardware encoder TEST PASSED"
        echo "   Output file: $ENCODE_OUTPUT ($FILE_SIZE bytes)"
        rm -f "$ENCODE_OUTPUT"
    else
        echo "   ✗ Hardware encoder TEST FAILED"
        echo ""
        echo "   Error output:"
        echo "$ENCODE_TEST" | grep -i "error\|failed\|could not" | sed 's/^/     /'
        echo ""
        echo "   Common causes:"
        echo "     - Permission denied on /dev/nvhost-nvenc"
        echo "     - Missing gstreamer1.0-plugins-bad"
        echo "     - nvv4l2h264enc not properly installed"
    fi
else
    echo "   ✗ SKIPPED - nvv4l2h264enc plugin not found"
fi

echo ""

# 7. Check application logs for actual errors
echo "7. Checking Application Logs:"
echo "   --------------------------"

if [ -d "logs" ]; then
    echo "   Recent errors from application logs:"
    echo ""

    for logfile in logs/*.log; do
        if [ -f "$logfile" ]; then
            echo "   From $(basename $logfile):"
            grep -i "error\|failed\|could not\|gstreamer" "$logfile" 2>/dev/null | tail -5 | sed 's/^/     /' || echo "     No errors found"
            echo ""
        fi
    done
else
    echo "   No logs directory found"
    echo "   Run your app first to generate logs"
fi

echo ""

# 8. Test Python OpenCV
echo "8. Python OpenCV Status:"
echo "   ---------------------"

python3 << 'PYEOF'
try:
    import cv2
    print(f"   ✓ OpenCV {cv2.__version__} installed")

    # Check GStreamer support
    build_info = cv2.getBuildInformation()
    has_gstreamer = 'GStreamer' in build_info and 'YES' in build_info.split('GStreamer')[1].split('\n')[0]

    if has_gstreamer:
        print("   ✓ OpenCV has GStreamer support")
    else:
        print("   ✗ OpenCV does NOT have GStreamer support")
        print("     This affects hardware decode via OpenCV")

except ImportError:
    print("   ✗ OpenCV not installed")
    print("     Install: pip3 install opencv-python")
PYEOF

echo ""

# Summary
echo "=========================================="
echo "SUMMARY & RECOMMENDATIONS"
echo "=========================================="
echo ""

ISSUES_FOUND=0

if [ $DECODER_OK -eq 0 ]; then
    echo "✗ CRITICAL: nvv4l2decoder plugin not found"
    echo "  Fix: sudo apt-get install gstreamer1.0-plugins-bad"
    echo ""
    ISSUES_FOUND=1
fi

if [ $ENCODER_OK -eq 0 ]; then
    echo "✗ CRITICAL: nvv4l2h264enc plugin not found"
    echo "  Fix: sudo apt-get install gstreamer1.0-plugins-bad"
    echo ""
    ISSUES_FOUND=1
fi

if ! groups | grep -q video; then
    echo "✗ WARNING: User not in 'video' group"
    echo "  Fix: sudo usermod -a -G video $USER"
    echo "       Then logout and login again"
    echo ""
    ISSUES_FOUND=1
fi

if [ $ISSUES_FOUND -eq 0 ]; then
    echo "✓ All hardware acceleration components appear to be installed"
    echo ""
    echo "If encoding/decoding still fails:"
    echo "  1. Check application logs: tail -f logs/*.log"
    echo "  2. Share the error messages"
    echo "  3. Verify RTSP stream is accessible"
else
    echo "Please fix the issues above and re-run this test."
fi

echo ""
echo "For detailed troubleshooting, check:"
echo "  - Application logs in logs/ directory"
echo "  - Run: journalctl -xe | grep nvhost"
echo "  - Run: dmesg | grep -i nvhost"
echo ""
