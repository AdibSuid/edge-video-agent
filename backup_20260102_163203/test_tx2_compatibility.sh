#!/bin/bash
# Test script for TX2 NX JetPack 4.5.1 compatibility
# Run this on your TX2 NX to check if hardware acceleration will work

echo "=========================================="
echo "TX2 NX JetPack 4.5.1 Compatibility Test"
echo "=========================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo -e "${RED}ERROR: Not running on a Jetson device${NC}"
    exit 1
fi

echo ""
echo "1. System Information"
echo "   -----------------"
cat /etc/nv_tegra_release
dpkg -l | grep nvidia-l4t-core | awk '{print "   L4T Version: " $3}'

echo ""
echo "2. OpenCV GStreamer Support (CRITICAL for hardware decode)"
echo "   --------------------------------------------------------"
python3 -c "
import cv2
import sys
info = cv2.getBuildInformation()
has_gstreamer = 'GStreamer' in info and 'YES' in info.split('GStreamer')[1].split('\n')[0]
print('   OpenCV Version:', cv2.__version__)
if has_gstreamer:
    print('   GStreamer Support: ✓ YES')
    print('   Status: Hardware decode will work')
    sys.exit(0)
else:
    print('   GStreamer Support: ✗ NO')
    print('   Status: Hardware decode will FAIL')
    print('   Fix: Rebuild OpenCV with -DWITH_GSTREAMER=ON')
    sys.exit(1)
" 2>/dev/null

OPENCV_GSTREAMER=$?

echo ""
echo "3. GStreamer V4L2 Plugins (Required for hardware acceleration)"
echo "   -----------------------------------------------------------"

# Check decoder
if gst-inspect-1.0 nvv4l2decoder > /dev/null 2>&1; then
    echo -e "   nvv4l2decoder: ${GREEN}✓ Available${NC}"
    DECODER_OK=1
else
    echo -e "   nvv4l2decoder: ${RED}✗ Not found${NC}"
    DECODER_OK=0
fi

# Check encoder
if gst-inspect-1.0 nvv4l2h264enc > /dev/null 2>&1; then
    echo -e "   nvv4l2h264enc: ${GREEN}✓ Available${NC}"
    ENCODER_OK=1
else
    echo -e "   nvv4l2h264enc: ${RED}✗ Not found${NC}"
    ENCODER_OK=0
fi

echo ""
echo "4. FFmpeg Hardware Encoder Support (Current code uses this)"
echo "   --------------------------------------------------------"

FFMPEG_HW_ENC=0
if ffmpeg -encoders 2>/dev/null | grep -q "h264_nvenc"; then
    echo -e "   h264_nvenc: ${GREEN}✓ Available${NC}"
    FFMPEG_HW_ENC=1
elif ffmpeg -encoders 2>/dev/null | grep -q "h264_v4l2m2m"; then
    echo -e "   h264_v4l2m2m: ${GREEN}✓ Available${NC}"
    FFMPEG_HW_ENC=1
else
    echo -e "   Hardware encoders: ${RED}✗ Not found${NC}"
    echo "   Available encoders:"
    ffmpeg -encoders 2>/dev/null | grep h264 | head -3 | sed 's/^/   /'
    FFMPEG_HW_ENC=0
fi

echo ""
echo "=========================================="
echo "COMPATIBILITY RESULTS"
echo "=========================================="

echo ""
echo "Current Code Behavior Prediction:"
echo ""

# Hardware Decode
if [ $OPENCV_GSTREAMER -eq 0 ] && [ $DECODER_OK -eq 1 ]; then
    echo -e "Hardware Decode: ${GREEN}✓ WILL WORK${NC}"
    echo "   • Uses GStreamer nvv4l2decoder"
    echo "   • OpenCV has GStreamer support"
    DECODE_STATUS="working"
elif [ $DECODER_OK -eq 1 ]; then
    echo -e "Hardware Decode: ${RED}✗ WILL FAIL${NC}"
    echo "   • GStreamer plugin available"
    echo "   • BUT OpenCV lacks GStreamer support"
    echo -e "   • ${YELLOW}FIX: Rebuild OpenCV with GStreamer${NC}"
    DECODE_STATUS="failed"
else
    echo -e "Hardware Decode: ${RED}✗ WILL FAIL${NC}"
    echo "   • nvv4l2decoder plugin not found"
    DECODE_STATUS="failed"
fi

echo ""

# Hardware Encode
if [ $FFMPEG_HW_ENC -eq 1 ]; then
    echo -e "Hardware Encode: ${GREEN}✓ WILL WORK${NC}"
    echo "   • FFmpeg has hardware encoder support"
    ENCODE_STATUS="working"
else
    echo -e "Hardware Encode: ${RED}✗ WILL FAIL${NC}"
    echo "   • FFmpeg lacks hardware encoder support"
    echo "   • Will fall back to software (libx264)"
    echo -e "   • ${YELLOW}Recommendation: Use GStreamer instead${NC}"
    ENCODE_STATUS="failed"
fi

echo ""
echo "=========================================="
echo "RECOMMENDATIONS"
echo "=========================================="
echo ""

if [ "$DECODE_STATUS" = "failed" ] || [ "$ENCODE_STATUS" = "failed" ]; then
    echo "Your current code will NOT achieve full hardware acceleration."
    echo ""

    if [ $OPENCV_GSTREAMER -ne 0 ]; then
        echo -e "${YELLOW}Priority 1: Fix OpenCV GStreamer Support${NC}"
        echo "   Without this, hardware decode won't work at all."
        echo "   See: JETPACK4_TX2_SETUP.md (section 3)"
        echo ""
    fi

    if [ $FFMPEG_HW_ENC -eq 0 ]; then
        echo -e "${YELLOW}Priority 2: Switch to GStreamer for Encoding${NC}"
        echo "   Current code uses FFmpeg (not community standard)"
        echo "   Recommendation: Use GStreamer nvv4l2h264enc"
        echo "   See: COMMUNITY_STANDARD_FIX.md"
        echo ""
    fi

    echo "Quick Fix Steps:"
    echo "   1. Run: chmod +x setup_tx2_nx_jp4.sh"
    echo "   2. Run: ./setup_tx2_nx_jp4.sh"
    echo "   3. Check if OpenCV needs rebuilding"
    echo "   4. Update encoding code to use GStreamer"
else
    echo -e "${GREEN}✓ Your system is ready for hardware acceleration!${NC}"
    echo ""
    echo "Note: Your encoding uses FFmpeg, which works but is not"
    echo "the community standard. Consider switching to GStreamer"
    echo "for better performance and maintainability."
fi

echo ""
echo "=========================================="
echo "Testing Hardware Capabilities (Optional)"
echo "=========================================="
echo ""
echo "Test hardware decode (GStreamer):"
echo "  gst-launch-1.0 videotestsrc num-buffers=100 ! 'video/x-raw,width=1920,height=1080' ! \\"
echo "    x264enc ! h264parse ! nvv4l2decoder ! fakesink"
echo ""
echo "Test hardware encode (GStreamer):"
echo "  gst-launch-1.0 videotestsrc num-buffers=100 ! 'video/x-raw,width=1920,height=1080' ! \\"
echo "    nvv4l2h264enc ! fakesink"
echo ""
