#!/bin/bash
# Edge Agent Installation Script for Linux

set -e

echo "=========================================="
echo "Edge Agent - Installation Script"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. Consider running as regular user."
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS. Exiting."
    exit 1
fi

echo "Detected OS: $OS"
echo ""

# Install system dependencies
echo "Installing system dependencies..."

case $OS in
    ubuntu|debian)
        sudo apt-get update
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            gstreamer1.0-tools \
            gstreamer1.0-plugins-base \
            gstreamer1.0-plugins-good \
            gstreamer1.0-plugins-bad \
            gstreamer1.0-plugins-ugly \
            gstreamer1.0-libav \
            libgstreamer1.0-dev \
            libgstreamer-plugins-base1.0-dev \
            python3-gst-1.0 \
            libopencv-dev \
            python3-opencv \
            git
        ;;
    
    fedora|rhel|centos)
        sudo dnf install -y \
            python3 \
            python3-pip \
            gstreamer1 \
            gstreamer1-plugins-base \
            gstreamer1-plugins-good \
            gstreamer1-plugins-bad-free \
            gstreamer1-plugins-ugly-free \
            gstreamer1-libav \
            python3-gobject \
            opencv \
            python3-opencv \
            git
        ;;
    
    arch)
        sudo pacman -S --noconfirm \
            python \
            python-pip \
            gstreamer \
            gst-plugins-base \
            gst-plugins-good \
            gst-plugins-bad \
            gst-plugins-ugly \
            gst-libav \
            python-gobject \
            opencv \
            python-opencv \
            git
        ;;
    
    *)
        echo "Unsupported OS: $OS"
        echo "Please install dependencies manually:"
        echo "  - Python 3.8+"
        echo "  - GStreamer 1.0+"
        echo "  - OpenCV 4+"
        exit 1
        ;;
esac

echo ""
echo "System dependencies installed successfully!"
echo ""

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "To start the Edge Agent:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the application: python app.py"
echo ""
echo "Web UI will be available at: http://localhost:5000"
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml to set your cloud SRT server address"
echo "  2. Configure Telegram bot (optional)"
echo "  3. Start discovering cameras!"
echo ""