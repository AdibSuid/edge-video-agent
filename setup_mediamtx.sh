#!/bin/bash
# Bash script to download and setup MediaMTX for Linux
# Run: chmod +x setup_mediamtx.sh && ./setup_mediamtx.sh

set -e

echo "========================================"
echo "MediaMTX RTSP Server Setup"
echo "========================================"
echo ""

# Configuration
MEDIAMTX_VERSION="v1.5.1"
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/$MEDIAMTX_VERSION/mediamtx_${MEDIAMTX_VERSION}_linux_amd64.tar.gz"
DOWNLOAD_FILE="mediamtx.tar.gz"

# Step 1: Download MediaMTX
echo "[1/5] Downloading MediaMTX $MEDIAMTX_VERSION..."

if [ -f "mediamtx" ]; then
    echo "  MediaMTX already exists. Skipping download."
else
    wget -q --show-progress -O "$DOWNLOAD_FILE" "$MEDIAMTX_URL"
    echo "  Download complete!"

    # Step 2: Extract
    echo "[2/5] Extracting MediaMTX..."
    tar -xzf "$DOWNLOAD_FILE"
    rm "$DOWNLOAD_FILE"
    chmod +x mediamtx
    echo "  Extraction complete!"
fi

# Step 3: Configure Firewall (if ufw is available)
echo "[3/5] Configuring firewall..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 8554/tcp
    echo "  Firewall rule added for port 8554!"
else
    echo "  ufw not found. Please manually configure firewall for port 8554"
fi

# Step 4: Get Public IP
echo "[4/5] Detecting public IP address..."
PUBLIC_IP=$(curl -s ifconfig.me)
if [ -n "$PUBLIC_IP" ]; then
    echo "  Your public IP: $PUBLIC_IP"
    echo ""
    echo "IMPORTANT: Update config.yaml with this IP:"
    echo "  edge_public_ip: '$PUBLIC_IP'"
else
    echo "  Could not detect public IP automatically"
fi

# Step 5: Create systemd service
echo "[5/5] Creating systemd service (optional)..."
read -p "Create systemd service for auto-start? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    WORK_DIR=$(pwd)
    SERVICE_FILE="/etc/systemd/system/mediamtx.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/mediamtx $WORK_DIR/mediamtx_config.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable mediamtx
    echo "  Systemd service created!"
    echo "  Start with: sudo systemctl start mediamtx"
    echo "  Check status: sudo systemctl status mediamtx"
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Update config.yaml with your public IP or domain"
echo "2. If behind router, configure port forwarding (8554 → this device)"
echo "3. Start MediaMTX: ./mediamtx ./mediamtx_config.yml"
echo "4. Start Edge Agent: python3 app.py"
echo ""
echo "For detailed instructions, see RTSP_RELAY_SETUP.md"
echo ""
