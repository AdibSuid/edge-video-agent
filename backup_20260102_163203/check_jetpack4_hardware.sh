#!/bin/bash
# Diagnostic script for Jetson TX2 NX JetPack 4 hardware acceleration

echo "========================================="
echo "Jetson TX2 NX Hardware Acceleration Check"
echo "========================================="
echo ""

# Check JetPack version
echo "1. JetPack Version:"
if [ -f /etc/nv_tegra_release ]; then
    cat /etc/nv_tegra_release
else
    echo "Not a Jetson device"
fi
echo ""

# Check for L4T version (should be 32.x for JP4)
echo "2. L4T Version:"
dpkg -l | grep nvidia-l4t-core | awk '{print $2, $3}'
echo ""

# Check GStreamer plugins
echo "3. GStreamer Plugins (for hardware decode):"
gst-inspect-1.0 | grep -E "omx|nvv4l2"
echo ""

# Check specific OMX decoder (JetPack 4)
echo "4. OMX H264 Decoder (JP4):"
gst-inspect-1.0 omxh264dec 2>/dev/null && echo "✓ omxh264dec available" || echo "✗ omxh264dec NOT available"
echo ""

# Check V4L2 decoder (JetPack 5)
echo "5. V4L2 Decoder (JP5):"
gst-inspect-1.0 nvv4l2decoder 2>/dev/null && echo "✓ nvv4l2decoder available (JP5)" || echo "✗ nvv4l2decoder NOT available (expected for JP4)"
echo ""

# Check FFmpeg encoders
echo "6. FFmpeg Encoders:"
ffmpeg -encoders 2>/dev/null | grep -E "h264_nvenc|h264_omx|h264_v4l2m2m"
echo ""

# Check FFmpeg decoders
echo "7. FFmpeg Decoders:"
ffmpeg -decoders 2>/dev/null | grep -E "h264_cuvid|h264"
echo ""

# Check for nvenc support
echo "8. NVENC Support:"
ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc | head -5
echo ""

# Check OpenCV version and CUDA support
echo "9. OpenCV + CUDA:"
python3 -c "import cv2; print('OpenCV:', cv2.__version__); print('CUDA devices:', cv2.cuda.getCudaEnabledDeviceCount() if hasattr(cv2, 'cuda') else 0)" 2>/dev/null || echo "OpenCV import failed"
echo ""

# Check GStreamer version
echo "10. GStreamer Version:"
gst-launch-1.0 --version 2>&1 | head -2
echo ""

echo "========================================="
echo "Summary:"
echo "For JetPack 4 (L4T 32.x), you should have:"
echo "  - omxh264dec (for decode)"
echo "  - omxh264enc (for encode)"
echo "  - OR h264_nvenc (FFmpeg)"
echo "========================================="
