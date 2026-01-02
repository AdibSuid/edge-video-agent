#!/bin/bash
# Quick test with proper authentication

echo "Testing authenticated RTSP pipeline..."
echo ""

# Proper authenticated URL from your config
RTSP_URL="rtsp://admin:tapway123@192.168.0.14:554/cam/realmonitor?channel=1&subtype=0"

echo "1. Quick connectivity test (5 seconds)..."
timeout 5 gst-launch-1.0 -v \
  rtspsrc location="$RTSP_URL" latency=200 protocols=tcp ! \
  fakesink

echo ""
echo "2. Testing full hardware pipeline (10 seconds, then auto-stop)..."
mkdir -p tmp/test_chunks

timeout 10 gst-launch-1.0 -e \
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
echo "✓ Test complete!"
ls -lh tmp/test_chunks/
echo ""
echo "Now run: python app.py"
