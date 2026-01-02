#!/bin/bash
# Test the fixed GStreamer pipeline to verify no "not-linked" errors

echo "Testing GStreamer hardware pipeline..."
echo ""

# Replace with your actual RTSP URL (with authentication)
RTSP_URL="rtsp://admin:tapway123@192.168.0.14:554/cam/realmonitor?channel=1&subtype=0"

# Test basic connectivity
echo "1. Testing RTSP connectivity..."
gst-launch-1.0 -v \
  rtspsrc location="$RTSP_URL" latency=200 protocols=tcp timeout=5000000 ! \
  fakesink \
  2>&1 | head -20

echo ""
echo "2. Testing hardware decode..."
gst-launch-1.0 -v \
  rtspsrc location="$RTSP_URL" latency=200 protocols=tcp ! \
  queue max-size-buffers=2 leaky=downstream ! \
  rtph264depay ! \
  h264parse ! \
  nvv4l2decoder enable-max-performance=1 ! \
  fakesink \
  2>&1 | head -30

echo ""
echo "3. Testing full pipeline (Ctrl+C to stop after a few seconds)..."
mkdir -p tmp/test_chunks

gst-launch-1.0 -e \
  rtspsrc location="$RTSP_URL" latency=200 protocols=tcp retry=3 timeout=10000000 ! \
  queue max-size-buffers=2 leaky=downstream ! \
  rtph264depay ! \
  h264parse ! \
  nvv4l2decoder enable-max-performance=1 ! \
  nvvidconv ! \
  "video/x-raw(memory:NVMM),format=I420" ! \
  nvv4l2h264enc bitrate=2000000 preset-level=1 insert-sps-pps=true ! \
  h264parse ! \
  splitmuxsink location=tmp/test_chunks/test_%05d.mp4 max-size-time=5000000000 max-files=5

echo ""
echo "✓ Test complete! Check tmp/test_chunks/ for output files."
