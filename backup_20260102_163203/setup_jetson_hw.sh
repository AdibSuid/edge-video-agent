#!/bin/bash
# Setup script for NVIDIA Jetson hardware acceleration

echo "================================================"
echo "NVIDIA Jetson Hardware Acceleration Setup"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Jetson
echo "1. Checking if running on NVIDIA Jetson..."
if [ -f /etc/nv_tegra_release ]; then
    echo -e "${GREEN}✓ Running on NVIDIA Jetson${NC}"
    cat /etc/nv_tegra_release
else
    echo -e "${RED}✗ Not running on NVIDIA Jetson${NC}"
    echo "This script is designed for NVIDIA Jetson platforms"
    exit 1
fi
echo ""

# Check for required GStreamer plugins
echo "2. Checking GStreamer NVIDIA plugins..."
if gst-inspect-1.0 nvv4l2decoder > /dev/null 2>&1; then
    echo -e "${GREEN}✓ nvv4l2decoder found${NC}"
else
    echo -e "${RED}✗ nvv4l2decoder NOT found${NC}"
    echo "Run: sudo apt-get install nvidia-jetpack"
fi

if gst-inspect-1.0 nvv4l2h264enc > /dev/null 2>&1; then
    echo -e "${GREEN}✓ nvv4l2h264enc found${NC}"
else
    echo -e "${RED}✗ nvv4l2h264enc NOT found${NC}"
    echo "Run: sudo apt-get install nvidia-jetpack"
fi
echo ""

# Check OpenCV GStreamer support
echo "3. Checking OpenCV GStreamer support..."
if python3 -c "import cv2; info = cv2.getBuildInformation(); print('YES' if 'GStreamer' in info and 'YES' in info.split('GStreamer')[1].split()[0] else 'NO')" | grep -q "YES"; then
    echo -e "${GREEN}✓ OpenCV built with GStreamer support${NC}"
else
    echo -e "${YELLOW}⚠ OpenCV may not have GStreamer support${NC}"
    echo "Consider rebuilding OpenCV with GStreamer enabled"
fi
echo ""

# Test hardware decoder
echo "4. Testing hardware decoder (5 second test)..."
if timeout 5 gst-launch-1.0 -e \
    videotestsrc num-buffers=100 ! \
    'video/x-raw,width=1280,height=720,framerate=25/1' ! \
    nvvidconv ! 'video/x-raw(memory:NVMM),format=I420' ! \
    nvv4l2h264enc ! h264parse ! \
    nvv4l2decoder ! fakesink > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Hardware decoder working${NC}"
else
    echo -e "${RED}✗ Hardware decoder test failed${NC}"
fi
echo ""

# Test hardware encoder
echo "5. Testing hardware encoder (5 second test)..."
if timeout 5 gst-launch-1.0 -e \
    videotestsrc num-buffers=100 ! \
    'video/x-raw,width=1280,height=720,framerate=25/1' ! \
    nvvidconv ! 'video/x-raw(memory:NVMM),format=I420' ! \
    nvv4l2h264enc bitrate=2000000 ! \
    h264parse ! qtmux ! fakesink > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Hardware encoder working${NC}"
else
    echo -e "${RED}✗ Hardware encoder test failed${NC}"
fi
echo ""

# Check for existing streamer.py
echo "6. Checking for existing streamer.py..."
if [ -f streamer.py ]; then
    echo -e "${YELLOW}⚠ Found existing streamer.py${NC}"
    echo "Creating backup: streamer_backup_$(date +%Y%m%d_%H%M%S).py"
    cp streamer.py "streamer_backup_$(date +%Y%m%d_%H%M%S).py"
    echo ""
    
    read -p "Replace with hardware-accelerated version? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f streamer_jetson_hw.py ]; then
            cp streamer_jetson_hw.py streamer.py
            echo -e "${GREEN}✓ Replaced streamer.py with hardware-accelerated version${NC}"
        else
            echo -e "${RED}✗ streamer_jetson_hw.py not found${NC}"
            echo "Please ensure streamer_jetson_hw.py is in the current directory"
        fi
    fi
else
    echo -e "${YELLOW}⚠ streamer.py not found in current directory${NC}"
    if [ -f streamer_jetson_hw.py ]; then
        cp streamer_jetson_hw.py streamer.py
        echo -e "${GREEN}✓ Created streamer.py from hardware-accelerated version${NC}"
    fi
fi
echo ""

# Update config.yaml
echo "7. Updating config.yaml..."
if [ -f config.yaml ]; then
    # Check if use_hardware_decode already exists
    if grep -q "use_hardware_decode" config.yaml; then
        echo -e "${GREEN}✓ Hardware acceleration already configured in config.yaml${NC}"
    else
        # Add hardware acceleration settings
        cat >> config.yaml << EOF

# Hardware acceleration settings (NVIDIA Jetson)
use_hardware_decode: true
use_hardware_encode: true
EOF
        echo -e "${GREEN}✓ Added hardware acceleration settings to config.yaml${NC}"
    fi
else
    echo -e "${YELLOW}⚠ config.yaml not found${NC}"
    echo "Please manually add to config.yaml:"
    echo "  use_hardware_decode: true"
    echo "  use_hardware_encode: true"
fi
echo ""

# Performance recommendations
echo "================================================"
echo "Performance Recommendations"
echo "================================================"
echo ""
echo "For optimal performance:"
echo ""
echo "1. Set Jetson to MAX performance mode:"
echo "   sudo nvpmodel -m 0"
echo "   sudo jetson_clocks"
echo ""
echo "2. Monitor GPU/encoder usage:"
echo "   sudo tegrastats"
echo ""
echo "3. Update config.yaml for your cameras:"
echo "   motion_detection_scale: 0.25  # Faster motion detection"
echo "   motion_frame_skip: 2           # Process every other frame"
echo "   default_bitrate: 2000000       # 2 Mbps per camera"
echo ""
echo "4. Test with single camera first, then scale up"
echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Review JETSON_HARDWARE_ACCELERATION_GUIDE.md"
echo "2. Test with: python app.py"
echo "3. Monitor performance with: sudo tegrastats"
echo ""