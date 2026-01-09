# Quick Start: RTSP Relay for Cloud DeepStream

## Why Do You Need This?

Your cameras have **local RTSP URLs** like `rtsp://192.168.1.133/stream1` which the cloud DeepStream server **cannot access** because it's on Alibaba Cloud.

The RTSP Relay makes your local cameras accessible to the cloud.

## Quick Setup (5 Minutes)

### 1. Install MediaMTX

**Windows:**
```powershell
.\setup_mediamtx.ps1
```

**Linux:**
```bash
chmod +x setup_mediamtx.sh
./setup_mediamtx.sh
```

### 2. Configure Your Public IP

Edit `config.yaml` and add your public IP:

```yaml
edge_public_ip: 'YOUR.PUBLIC.IP'  # e.g., '203.0.113.45'
rtsp_relay_port: 8554
```

**Find your public IP:**
- Visit: https://whatismyipaddress.com/
- Or run: `curl ifconfig.me`

### 3. Open Firewall Port

**CRITICAL:** Port 8554 must be accessible from the internet.

**Windows:**
```powershell
New-NetFirewallRule -DisplayName "RTSP Relay" -Direction Inbound -Protocol TCP -LocalPort 8554 -Action Allow
```

**Linux:**
```bash
sudo ufw allow 8554/tcp
```

**Router Port Forwarding:**
If your edge device is behind a router, forward port 8554:
- Log into router admin (usually http://192.168.1.1)
- Navigate to Port Forwarding / NAT
- Forward: External port 8554 → Edge device's local IP → Port 8554

### 4. Start Services

**Terminal 1** - Start MediaMTX:
```bash
# Windows
.\mediamtx.exe .\mediamtx_config.yml

# Linux
./mediamtx ./mediamtx_config.yml
```

**Terminal 2** - Start Edge Agent:
```bash
python app.py
```

### 5. Verify

Check the logs for:
```
Starting RTSP relay: Test
  Local source: rtsp://orinnano:orinnano@192...
  Public access: rtsp://YOUR.IP:8554/Test
✓ RTSP relay started for Test
✓ Added stream to DeepStream: Test
  Public URL: rtsp://YOUR.IP:8554/Test
```

## How It Works

```
Camera → FFmpeg Relay → MediaMTX → Internet → DeepStream
(local)    (auto)      (port 8554)  (public)   (cloud)
```

1. **FFmpeg** pulls from your local camera
2. **FFmpeg** pushes to **MediaMTX** (local RTSP server on port 8554)
3. **MediaMTX** exposes stream via your public IP
4. **DeepStream** connects to `rtsp://YOUR_IP:8554/camera_id`

## Troubleshooting

### Can't access from internet?

Test from another machine:
```bash
ffplay rtsp://YOUR_PUBLIC_IP:8554/Test
```

If fails:
- ❌ Firewall blocking port 8554
- ❌ Router not forwarding port 8554
- ❌ Wrong public IP in config.yaml

### MediaMTX not receiving streams?

Check MediaMTX console for errors. You should see:
```
INF [RTSP] [conn] opened
INF [RTSP] [session] created
```

### DeepStream can't connect?

From DeepStream server, test connectivity:
```bash
curl telnet://YOUR_PUBLIC_IP:8554
```

Should connect. If not, port 8554 is not accessible.

## Need Help?

See full documentation: `RTSP_RELAY_SETUP.md`
