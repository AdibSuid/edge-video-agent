# Quick Start Guide

## Linux (Ubuntu/Debian)

### 1. Install System Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv \
    gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    python3-gst-1.0 python3-opencv
```

### 2. Run Installation Script
```bash
chmod +x install.sh
./install.sh
```

### 3. Configure
```bash
nano config.yaml
```

Update these fields:
- `cloud_srt_host`: Your cloud server address (e.g., `srt://cloud.example.com:9000`)
- `srt_passphrase`: Strong encryption password

### 4. Start Application
```bash
source venv/bin/activate
python app.py
```

### 5. Access Web UI
Open browser: `http://localhost:5000`

---

## Windows

### 1. Install Python
Download and install Python 3.8+ from [python.org](https://www.python.org/)
- ✅ Check "Add Python to PATH" during installation

### 2. Install GStreamer
1. Download from [gstreamer.freedesktop.org](https://gstreamer.freedesktop.org/download/)
2. Install both "runtime" and "development" installers
3. Add to PATH: `C:\gstreamer\1.0\msvc_x86_64\bin`

### 3. Run Installation Script
```batch
install.bat
```

### 4. Configure
Edit `config.yaml` with Notepad:
- Update `cloud_srt_host`
- Update `srt_passphrase`

### 5. Start Application
```batch
venv\Scripts\activate
python app.py
```

### 6. Access Web UI
Open browser: `http://localhost:5000`

---

## First Time Setup

### 1. Add Your First Camera

**Option A: ONVIF Discovery**
1. Click "Discover Cameras"
2. Wait for scan to complete
3. Click "Add" on discovered camera
4. Enter RTSP URL (username and password)

**Option B: Manual Addition**
1. Click "Add Manual"
2. Enter camera name (e.g., "Front Door")
3. Enter RTSP URL:
   ```
   rtsp://admin:password@192.168.1.100:554/stream
   ```
4. Click "Test Connection"
5. Click "Add Camera"

### 2. Configure Motion Detection

1. Click "Motion Settings"
2. Draw zones by clicking on canvas
3. Adjust sensitivity slider (start at 25)
4. Set minimum area (start at 500)
5. Click "Save Settings"

### 3. Monitor Activity

1. Return to Dashboard
2. Watch network speed graph
3. See motion status on camera cards
4. Check "Event Log" for history

---

## Testing the System

### Test 1: Camera Connection
```bash
# On Linux/Mac
vlc rtsp://admin:password@192.168.1.100:554/stream

# On Windows
# Use VLC Media Player → Media → Open Network Stream
```

### Test 2: Motion Detection
1. Add camera with motion detection
2. Wave in front of camera
3. Watch FPS change from 1 to 25
4. Check "Event Log" for motion events

### Test 3: Network Adaptation
1. Run speed test
2. If below threshold, quality should reduce automatically
3. Check Telegram for alerts (if configured)

---

## Common RTSP URLs

Replace `IP`, `USER`, and `PASS` with your values:

**Hikvision:**
```
rtsp://USER:PASS@IP:554/Streaming/Channels/101
```

**Dahua:**
```
rtsp://USER:PASS@IP:554/cam/realmonitor?channel=1&subtype=0
```

**Reolink:**
```
rtsp://USER:PASS@IP:554/h264Preview_01_main
```

**Amcrest:**
```
rtsp://USER:PASS@IP:554/cam/realmonitor?channel=1&subtype=0
```

**Generic/Others:**
```
rtsp://USER:PASS@IP:554/stream
rtsp://USER:PASS@IP:554/live
rtsp://USER:PASS@IP:554/video1
```

---

## Troubleshooting

### "GStreamer not found"
- **Linux**: Run `sudo apt-get install gstreamer1.0-tools`
- **Windows**: Reinstall GStreamer and verify PATH

### "Camera connection failed"
1. Test URL with VLC first
2. Verify username/password
3. Check camera is on same network
4. Try different RTSP paths

### "High CPU usage"
1. Reduce resolution in config.yaml:
   ```yaml
   normal_resolution: "640x360"
   ```
2. Limit active cameras
3. Adjust motion detection zones

### "Port 5000 in use"
Change port in config.yaml:
```yaml
web_port: 8080
```

---

## Next Steps

1. ✅ Add multiple cameras
2. ✅ Fine-tune motion zones
3. ✅ Set up Telegram notifications
4. ✅ Configure cloud SRT server
5. ✅ Monitor bandwidth savings
6. ✅ Review event logs regularly

---

## Need Help?

1. Check README.md for detailed documentation
2. Review logs in `logs/` directory
3. Verify GStreamer: `gst-launch-1.0 --version`
4. Test Python imports:
   ```python
   import cv2
   import gi
   gi.require_version('Gst', '1.0')
   from gi.repository import Gst
   ```

**Enjoy your Edge Agent!** 🎥