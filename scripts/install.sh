#!/bin/bash
set -e

echo "Edge Video Agent - Installation Script"
echo "======================================"

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "Detected OS: ${MACHINE}"

echo ""
echo "Installing dependencies..."

if [ "$MACHINE" == "Linux" ]; then
    if [ -f /etc/debian_version ]; then
        apt-get update
        apt-get install -y ffmpeg ca-certificates
    elif [ -f /etc/redhat-release ]; then
        yum install -y epel-release
        yum install -y ffmpeg ca-certificates
    else
        echo "Unsupported Linux distribution"
        exit 1
    fi
elif [ "$MACHINE" == "Mac" ]; then
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Please install Homebrew first."
        exit 1
    fi
    brew install ffmpeg
else
    echo "Unsupported operating system"
    exit 1
fi

echo "Dependencies installed successfully"

echo ""
echo "Creating user and directories..."

if ! id "edge-agent" &>/dev/null; then
    if [ "$MACHINE" == "Linux" ]; then
        useradd -r -s /bin/false edge-agent
    elif [ "$MACHINE" == "Mac" ]; then
        dscl . -create /Users/edge-agent
        dscl . -create /Users/edge-agent UserShell /usr/bin/false
    fi
    echo "User 'edge-agent' created"
else
    echo "User 'edge-agent' already exists"
fi

mkdir -p /etc/edge-agent/certs
mkdir -p /var/lib/edge-agent/buffer
mkdir -p /var/log/edge-agent

chown -R edge-agent:edge-agent /var/lib/edge-agent /var/log/edge-agent
chmod 750 /etc/edge-agent
chmod 700 /etc/edge-agent/certs

echo "Directories created"

echo ""
echo "Installing binary..."

if [ -f "bin/edge-agent" ]; then
    cp bin/edge-agent /usr/local/bin/
    chmod 755 /usr/local/bin/edge-agent
    echo "Binary installed to /usr/local/bin/edge-agent"
else
    echo "Binary not found. Please build first with 'make build'"
    exit 1
fi

echo ""
echo "Installing configuration..."

if [ ! -f "/etc/edge-agent/config.yaml" ]; then
    cp configs/config.example.yaml /etc/edge-agent/config.yaml
    echo "Configuration installed to /etc/edge-agent/config.yaml"
    echo "IMPORTANT: Edit /etc/edge-agent/config.yaml with your settings"
else
    echo "Configuration already exists at /etc/edge-agent/config.yaml"
fi

if [ "$MACHINE" == "Linux" ]; then
    echo ""
    echo "Installing systemd service..."
    
    cp deployments/systemd/edge-agent.service /etc/systemd/system/
    systemctl daemon-reload
    
    echo "Systemd service installed"
    echo ""
    echo "To enable and start the service:"
    echo "  sudo systemctl enable edge-agent"
    echo "  sudo systemctl start edge-agent"
    echo ""
    echo "To check status:"
    echo "  sudo systemctl status edge-agent"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u edge-agent -f"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit configuration: /etc/edge-agent/config.yaml"
echo "2. Add TLS certificates (if using mutual TLS): /etc/edge-agent/certs/"
echo "3. Start the service or run manually"
echo ""
echo "Manual run: /usr/local/bin/edge-agent -config /etc/edge-agent/config.yaml"