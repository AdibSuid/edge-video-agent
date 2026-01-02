#!/bin/bash
# Hardware encoder/decoder detection script for Raspberry Pi

echo "=========================================="
echo "Hardware Video Support Detection"
echo "=========================================="
echo ""

echo "1. System Information:"
echo "   OS: $(uname -a)"
echo "   Device: $(cat /proc/device-tree/model 2>/dev/null || echo 'Unknown')"
echo ""

echo "2. FFmpeg Version:"
ffmpeg -version | head -n 1
echo ""

echo "3. Available Video Devices:"
ls -la /dev/video* 2>/dev/null || echo "   No /dev/video* devices found"
echo ""

echo "4. FFmpeg Encoders (H.264):"
echo "   Looking for: h264_v4l2m2m, h264_omx, libx264..."
ffmpeg -encoders 2>/dev/null | grep h264 || echo "   No H.264 encoders found"
echo ""

echo "5. FFmpeg Decoders (H.264):"
echo "   Looking for: h264_v4l2m2m, h264_mmal..."
ffmpeg -decoders 2>/dev/null | grep h264 || echo "   No H.264 decoders found"
echo ""

echo "6. Hardware Encoding Test:"
echo "   Testing h264_v4l2m2m encoder..."
timeout 5 ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=10 \
  -c:v h264_v4l2m2m -b:v 1M -f null - 2>&1 | grep -q "Encoder h264_v4l2m2m"
if [ $? -eq 0 ]; then
    echo "   ✓ h264_v4l2m2m encoder AVAILABLE"
else
    echo "   ✗ h264_v4l2m2m encoder NOT AVAILABLE"
fi
echo ""

echo "7. Software Encoding Test (libx264):"
echo "   Testing libx264 encoder with ultrafast preset..."
timeout 5 ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=10 \
  -c:v libx264 -preset ultrafast -crf 28 -f null - 2>&1 | grep -q "libx264"
if [ $? -eq 0 ]; then
    echo "   ✓ libx264 encoder AVAILABLE (software encoding)"
else
    echo "   ✗ libx264 encoder NOT AVAILABLE"
fi
echo ""

echo "8. Recommendations:"
echo ""
if lsmod | grep -q v4l2; then
    echo "   ✓ V4L2 kernel module loaded"
else
    echo "   ⚠ V4L2 kernel module not loaded (may need: sudo modprobe v4l2_mem2mem)"
fi
echo ""

if [ -f /boot/firmware/config.txt ]; then
    echo "   Checking /boot/firmware/config.txt for GPU settings..."
    grep -E "gpu_mem|dtoverlay.*v4l2" /boot/firmware/config.txt 2>/dev/null || echo "   No GPU/V4L2 settings found in config.txt"
elif [ -f /boot/config.txt ]; then
    echo "   Checking /boot/config.txt for GPU settings..."
    grep -E "gpu_mem|dtoverlay.*v4l2" /boot/config.txt 2>/dev/null || echo "   No GPU/V4L2 settings found in config.txt"
fi
echo ""

echo "=========================================="
echo "Summary:"
echo "=========================================="
echo "For Raspberry Pi 5:"
echo "  - Hardware H.264 encoding is EXPERIMENTAL/LIMITED"
echo "  - Use 'encoding_preset: ultrafast' for best CPU efficiency"
echo "  - Monitor logs for 'Hardware encoding failed' messages"
echo "  - Hardware decode may work better than encode on Pi 5"
echo ""
echo "Check your application logs for actual encoder usage:"
echo "  grep -i 'encoding' /path/to/your/logs"
echo "=========================================="
