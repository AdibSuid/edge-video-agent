#!/bin/bash
# Quick setup script for Jetson Orin Nano Super

set -e

echo "========================================="
echo "  Edge Video Agent - Jetson Setup"
echo "========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Warning: This script is optimized for Jetson platforms"
    read -p "Continue anyway? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Set to max performance
echo "Setting Jetson to maximum performance mode..."
sudo nvpmodel -m 0 2>/dev/null || echo "Note: nvpmodel not available"
sudo jetson_clocks 2>/dev/null || echo "Note: jetson_clocks not available"

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv ffmpeg

# Check OpenCV CUDA support
echo ""
echo "Checking OpenCV CUDA support..."
python3 -c "import cv2; print('OpenCV version:', cv2.__version__); print('CUDA devices:', cv2.cuda.getCudaEnabledDeviceCount())" || {
    echo "Warning: OpenCV CUDA support not detected"
    echo "The system will work but won't use GPU acceleration"
    echo "See JETSON_SETUP.md for instructions on building OpenCV with CUDA"
}

# Create virtual environment with system site packages (for OpenCV CUDA)
echo ""
echo "Creating Python virtual environment (with system-site-packages for CUDA)..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install Flask PyYAML numpy psutil requests onvif-zeep zeep

# Run hardware detection
echo ""
echo "Running hardware detection..."
python3 detect_hardware.py

# Copy optimized config if needed
if [ ! -f config.yaml ]; then
    echo ""
    echo "Creating default configuration from Jetson template..."
    cp config.jetson.yaml config.yaml
    echo "✓ Created config.yaml"
    echo "  Please edit config.yaml to add your camera RTSP URLs"
else
    echo ""
    echo "config.yaml already exists - not overwriting"
    echo "  See config.jetson.yaml for Jetson-optimized settings"
fi

# Make scripts executable
chmod +x detect_hardware.py
chmod +x monitor_performance.sh 2>/dev/null || true

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your camera RTSP URLs"
echo "  2. Activate virtual environment: source venv/bin/activate"
echo "  3. Start the application: python3 app.py"
echo "  4. Access web interface: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "To monitor performance:"
echo "  sudo tegrastats"
echo "  or"
echo "  sudo jtop"
echo ""
