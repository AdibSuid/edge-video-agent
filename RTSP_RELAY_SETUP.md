# RTSP Relay Setup for Cloud DeepStream Access

## Problem

Your edge device has cameras on a **local network** (e.g., `192.168.1.x`), but your DeepStream server runs on **Alibaba Cloud**. DeepStream cannot access the local RTSP URLs directly.

## Solution

Use **RTSP Relay** to make local camera streams accessible to the cloud:

```
Local Cameras → Edge Device (RTSP Relay) → Cloud DeepStream
192.168.1.x  →  Public IP:8554/{cam_id}  →  47.250.210.53
```

## Architecture

1. **MediaMTX**: RTSP server running on edge device (port 8554)
2. **FFmpeg Relays**: Pull from local cameras, push to MediaMTX
3. **DeepStream**: Pulls from MediaMTX via edge device's public IP

```
┌─────────────────────────────────────────┐
│         Edge Device (192.168.1.x)       │
│                                         │
│  Camera1 ─┐                             │
│           │                             │
│  Camera2 ─┤─► FFmpeg ─► MediaMTX:8554  │ ─► Public IP:8554
│           │     Relay      (RTSP Server)│       (Internet)
│  Camera3 ─┘                             │              │
│                                         │              │
└─────────────────────────────────────────┘              │
                                                         │
                                                         ▼
                                          ┌──────────────────────┐
                                          │ DeepStream (Cloud)   │
                                          │ 47.250.210.53        │
                                          └──────────────────────┘
```

## Setup Instructions

### Step 1: Download MediaMTX

MediaMTX is a lightweight RTSP server (5MB executable).

**Windows:**
```bash
# Download from GitHub releases
https://github.com/bluenviron/mediamtx/releases/latest

# Or use PowerShell:
Invoke-WebRequest -Uri "https://github.com/bluenviron/mediamtx/releases/download/v1.5.1/mediamtx_v1.5.1_windows_amd64.zip" -OutFile "mediamtx.zip"
Expand-Archive -Path "mediamtx.zip" -DestinationPath "."
```

**Linux:**
```bash
wget https://github.com/bluenviron/mediamtx/releases/download/v1.5.1/mediamtx_v1.5.1_linux_amd64.tar.gz
tar -xzf mediamtx_v1.5.1_linux_amd64.tar.gz
```

### Step 2: Configure MediaMTX

The `mediamtx_config.yml` file is already created. Key settings:

```yaml
rtspAddress: :8554  # RTSP port
logLevel: info
```

### Step 3: Configure Edge Device Public IP

Edit `config.yaml`:

```yaml
# Option 1: Use Public IP
edge_public_ip: '203.0.113.45'  # Replace with your actual public IP

# Option 2: Use Domain Name (recommended)
edge_public_domain: 'edge1.mydomain.com'

rtsp_relay_port: 8554
```

**Find your public IP:**
```bash
# Windows/Linux:
curl ifconfig.me
# Or visit: https://whatismyipaddress.com/
```

### Step 4: Open Firewall Port

**Important:** Port 8554 must be accessible from the internet for DeepStream to connect.

**Windows Firewall:**
```powershell
New-NetFirewallRule -DisplayName "RTSP Relay" -Direction Inbound -Protocol TCP -LocalPort 8554 -Action Allow
```

**Linux (ufw):**
```bash
sudo ufw allow 8554/tcp
```

**Router Port Forwarding:**
- Log into your router admin panel
- Forward external port `8554` to edge device's local IP on port `8554`
- Example: External `203.0.113.45:8554` → Internal `192.168.1.100:8554`

### Step 5: Start MediaMTX

**Windows:**
```bash
# Start MediaMTX in a new terminal
mediamtx.exe mediamtx_config.yml
```

**Linux:**
```bash
# Start MediaMTX as background service
./mediamtx mediamtx_config.yml &
```

**As a Service (Linux systemd):**
```bash
sudo nano /etc/systemd/system/mediamtx.service
```

```ini
[Unit]
Description=MediaMTX RTSP Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/edge-video-agent
ExecStart=/path/to/mediamtx /path/to/mediamtx_config.yml
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
sudo systemctl status mediamtx
```

### Step 6: Start Edge Agent

```bash
python app.py
```

The edge agent will automatically:
1. Start FFmpeg relays for each camera
2. Push streams to MediaMTX
3. Send public RTSP URLs to DeepStream

## Verification

### Test Local RTSP Relay

```bash
# Test if MediaMTX is receiving the stream
ffplay rtsp://localhost:8554/Test
# or
vlc rtsp://localhost:8554/Test
```

### Test Public Access

From another machine (or cloud server):
```bash
# Replace with your public IP
ffplay rtsp://203.0.113.45:8554/Test
```

### Check DeepStream Connection

```bash
# Query DeepStream for active streams
curl http://47.250.210.53:9002/api/v1/stream/get-stream-info
```

Expected output:
```json
{
  "message": {
    "stream_info": [
      {
        "camera_id": "Test",
        "camera_url": "rtsp://203.0.113.45:8554/Test"
      }
    ]
  }
}
```

## Troubleshooting

### Issue: DeepStream can't connect

**Check:**
1. Firewall port 8554 is open
2. Router port forwarding is configured
3. `edge_public_ip` in config.yaml is correct
4. MediaMTX is running: `ps aux | grep mediamtx`

**Test:**
```bash
# From DeepStream server
curl telnet://YOUR_PUBLIC_IP:8554
# Should connect
```

### Issue: FFmpeg relay fails

**Check logs:**
```bash
# Look for relay errors in console output
# Check MediaMTX logs for incoming connections
```

**Manual test:**
```bash
# Test FFmpeg can push to MediaMTX
ffmpeg -rtsp_transport tcp \
  -i rtsp://camera_ip/stream1 \
  -c copy -f rtsp \
  rtsp://localhost:8554/test_stream
```

### Issue: High bandwidth usage

MediaMTX uses **copy codec** (no re-encoding), so bandwidth = camera bitrate × number of consumers.

**Solutions:**
1. Reduce camera bitrate in camera settings
2. Use lower resolution streams
3. Enable MediaMTX on-demand publishing (only stream when DeepStream connects)

## Network Requirements

- **Upload bandwidth**: ~2-4 Mbps per camera (depends on camera bitrate)
- **Latency**: Should be < 100ms for good performance
- **Firewall**: Port 8554 TCP must be open

## Security Considerations

### Add Authentication

Edit `mediamtx_config.yml`:
```yaml
authMethod: internal

paths:
  all:
    publishUser: edgedevice
    publishPass: your_secure_password
    readUser: deepstream
    readPass: another_secure_password
```

Update config.yaml:
```yaml
edge_public_ip: 'username:password@203.0.113.45'
```

### Use RTSPS (RTSP over TLS)

For production, consider using RTSPS for encryption.

## Alternative: VPN/Tunnel

If port forwarding is not possible, consider:
- **ZeroTier**: Virtual private network
- **Tailscale**: WireGuard-based mesh VPN
- **Ngrok**: RTSP tunneling service
