# Edge Agent - Motion-Triggered Video Streaming

A lightweight edge video surveillance agent that converts local CCTV streams to secure, cloud-ready video feeds with intelligent bandwidth optimization through motion detection.

## 🎯 Key Features

- **ONVIF Discovery**: Automatically find IP cameras on your network
- **Manual RTSP Addition**: Add any RTSP-compatible camera manually
- **Motion-Triggered Adaptive FPS**: 
  - **Idle**: 1 FPS (saves ~90% bandwidth)
  - **Motion**: 25 FPS (full quality)
- **Cloud Video Upload**: Automatic chunk upload with bearer token authentication
- **Secure Streaming**: AES-256 encrypted SRT streaming to cloud
- **Network Monitoring**: Real-time upload speed tracking
- **Adaptive Quality**: Automatic resolution reduction on slow connections
- **Telegram Alerts**: Get notified of connectivity issues
- **Web UI**: Easy-to-use browser interface with cloud upload status
- **Draggable Motion Zones**: Define specific areas for motion detection
- **Event Logging**: Track all motion events with timeline visualization
- **Upload Queue**: Automatic retry and queue management for cloud uploads
- **Cross-Platform**: Works on Windows and Linux
- **CPU-Only**: No GPU required (~15% CPU on 720p)

## 📋 Requirements

### Hardware
- CPU: Intel i5 or equivalent (Raspberry Pi 4 works for 640×360)
- RAM: 2GB minimum
- Network: Stable internet connection
- Storage: 500MB for application

### Software
- **Python**: 3.8 or higher
- **GStreamer**: 1.0 or higher (required for video processing)
- **OpenCV**: 4.0 or higher (installed via pip)
- **Operating System**: Windows 10+, Linux (Ubuntu 20.04+, Debian, Fedora, Arch)

## 🚀 Quick Start

### Linux Installation

```bash
# Clone or download the repository
cd edge-agent-motion

# Run installation script
chmod +x install.sh
./install.sh

# Activate virtual environment
source venv/bin/activate

# Edit configuration
nano config.yaml

# Start the agent
python app.py
```

### Windows Installation

```batch
# Run installation script
install.bat

# Install GStreamer manually (follow on-screen instructions)

# Activate virtual environment
venv\Scripts\activate

# Edit configuration
notepad config.yaml

# Start the agent
python app.py
```

### Access Web UI

Open your browser and navigate to: `http://localhost:5000`

## ⚙️ Configuration

Edit `config.yaml` to configure the agent:

```yaml
# Cloud SRT Server
cloud_srt_host: "srt://your-cloud-server:9000"
srt_passphrase: "your-secure-passphrase-here"

# Cloud Video Chunk Upload (Production)
cloud_upload_url: "https://your-cloud-server.com"  # Production cloud server URL
cloud_username: "your_username"                     # Cloud server username
cloud_password: "your_password"                     # Cloud server password
cloud_upload_enabled: true                          # Enable cloud upload

# Video Quality
normal_resolution: "1280x720"  # Normal quality
low_resolution: "640x360"      # Low bandwidth mode

# Motion Detection
motion_sensitivity: 25         # 0-255 (lower = more sensitive)
motion_min_area: 500          # Minimum pixels to trigger
motion_cooldown: 10           # Seconds to stay in high FPS
motion_low_fps: 1             # FPS when idle
motion_high_fps: 25           # FPS when motion detected
motion_zones: []              # Define via Web UI

# Network Monitoring
upload_speed_threshold_mbps: 2  # Switch to low quality below this

# Telegram Alerts (Optional)
telegram_bot_token: ""        # Your bot token
telegram_chat_id: ""          # Your chat ID

# Web UI
web_port: 5000
web_host: "0.0.0.0"
```

## ☁️ Cloud Upload Setup

The agent automatically uploads motion-triggered video chunks to your cloud server with bearer token authentication.

### Development/Testing with Mock Server

For testing without a real cloud server:

```bash
# Terminal 1: Start mock cloud server
python mock_cloud_server.py

# Terminal 2: Update config.yaml
cloud_upload_url: 'http://localhost:8000'
cloud_username: tapway
cloud_password: tapwaysuperadmin
cloud_upload_enabled: true

# Start edge agent
python app.py
```

The mock server will save uploaded chunks to `mock_cloud_storage/` directory.

### Production Setup with Real Cloud Server

When your cloud server is ready:

1. **Update `config.yaml`** with production credentials:
```yaml
cloud_upload_url: "https://your-production-server.com"
cloud_username: "your_production_username"
cloud_password: "your_production_password"
cloud_upload_enabled: true
```

2. **Verify cloud server endpoints** are available:
   - `POST /auth/login` - Authentication endpoint
   - `POST /streams/upload-chunk` - Chunk upload endpoint

3. **Expected API behavior:**
   - **Authentication**: Returns `{"access_token": "..."}` with 1-hour expiry
   - **Upload**: Accepts multipart form with `file`, `stream_id`, `ts_start`, `ts_end`
   - **Authorization**: Bearer token in `Authorization` header

4. **Monitor upload status** in the dashboard:
   - **Connected** (green) - Uploading successfully
   - **Auth Failed** (red) - Check credentials
   - **Disabled** (gray) - Enable in config.yaml

5. **Check logs** for upload activity:
```bash
tail -f logs/cloud_upload.log
```

### Cloud Upload Features

- ✅ **Automatic authentication** with token refresh
- ✅ **Upload queue** with retry logic
- ✅ **Real-time status** in web dashboard
- ✅ **Timestamp metadata** (ts_start, ts_end)
- ✅ **Stream identification** (cam1, cam2, etc.)
- ✅ **Error logging** for troubleshooting

### Troubleshooting Cloud Upload

**Queue growing:**
- Check network connectivity to cloud server
- Verify server is accepting uploads
- Check logs for authentication errors

**Auth Failed status:**
- Verify username/password in config.yaml
- Check cloud server `/auth/login` endpoint
- Ensure server returns valid access_token

**No uploads:**
- Verify `cloud_upload_enabled: true`
- Check motion detection is triggering
- Verify chunks are being created in `tmp/chunks/`

## 📱 Telegram Setup (Optional)

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add credentials to `config.yaml`

## 🚀 SRT Streaming to DeepStream Triton Inference

This edge agent can stream video to NVIDIA DeepStream for real-time AI inference (object detection, tracking, analytics).

### Architecture
```
Edge Agent → SRT Stream (encrypted) → DeepStream Server → Triton Inference → Analytics
```

### Configuration for DeepStream

**1. Configure SRT Server in `config.yaml`:**
```yaml
# SRT Streaming to DeepStream Triton Inference Server
cloud_srt_host: srt://192.168.1.200:9000  # DeepStream server IP
srt_passphrase: UuX7jgf7yWYRa6aMQ6y6w_d7mTMVtaK4CNEqENeZ0Hg
srt_mode: caller  # Edge initiates connection
srt_params:
  latency: 200    # 200ms for real-time inference
  maxbw: -1       # No bandwidth limit
  pbkeylen: 16    # AES-128 encryption

streams:
  - id: cam1
    srt_port: 9001  # Each camera gets unique port
    streaming_enabled: true
  - id: cam2
    srt_port: 9002
    streaming_enabled: true
```

**2. DeepStream Server Setup (Listener Mode):**

On your DeepStream/Triton server, configure to listen on SRT ports:

```python
# DeepStream config (deepstream_app_config.txt)
[source0]
enable=1
type=4  # SRT source
uri=srt://0.0.0.0:9001?mode=listener&passphrase=UuX7jgf7yWYRa6aMQ6y6w_d7mTMVtaK4CNEqENeZ0Hg

[source1]
enable=1
type=4
uri=srt://0.0.0.0:9002?mode=listener&passphrase=UuX7jgf7yWYRa6aMQ6y6w_d7mTMVtaK4CNEqENeZ0Hg
```

**3. Test Connection:**
```bash
# On DeepStream server, test SRT listener:
gst-launch-1.0 srtsrc uri="srt://:9001?mode=listener" ! decodebin ! autovideosink

# On edge agent, start streaming:
python app.py
```

### DeepStream Pipeline Integration

**Multi-Stream Inference Example:**
```python
# Each edge camera streams to different port
# DeepStream receives all streams and runs inference

Edge Agent (cam1:9001) ──┐
Edge Agent (cam2:9002) ──┼──→ DeepStream → Triton (YOLOv5/TAO) → Analytics
Edge Agent (cam3:9003) ──┘
```

### Benefits of SRT + DeepStream

- ✅ **Low Latency**: 200ms end-to-end with motion-triggered FPS
- ✅ **Encrypted**: AES-128/256 encryption in transit
- ✅ **Adaptive**: Automatic quality adjustment on slow networks
- ✅ **Scalable**: Multiple cameras to single DeepStream instance
- ✅ **Real-time**: 25 FPS during motion for AI inference
- ✅ **Efficient**: 1 FPS idle mode saves bandwidth

### Firewall Configuration

**On DeepStream Server:**
```bash
# Allow SRT ports for each camera
sudo ufw allow 9001/udp
sudo ufw allow 9002/udp
sudo ufw allow 9003/udp
```

**On Edge Agent (Windows):**
```powershell
# Test connectivity
Test-NetConnection -ComputerName 192.168.1.200 -Port 9001
```

### Troubleshooting SRT Connection

**Connection Refused:**
- Verify DeepStream is running in listener mode
- Check firewall allows UDP ports
- Ensure passphrase matches on both sides

**High Latency:**
- Reduce `latency` parameter (100-200ms recommended)
- Check network bandwidth with `iperf3`
- Verify motion detection is working (should be 25 FPS during motion)

**Stream Drops:**
- Increase `maxbw` if limited
- Check CPU usage on edge device
- Monitor network quality in dashboard

## 🎥 Adding Cameras

### Method 1: ONVIF Discovery
1. Go to **Discover Cameras**
2. Click **Start Discovery**
3. Select found cameras and add them

### Method 2: Manual Addition
1. Go to **Add Manual**
2. Enter camera name and RTSP URL
3. Test connection
4. Click **Add Camera**

### Common RTSP URL Formats

**Generic:**
```
rtsp://username:password@ip:port/stream
```

**Hikvision:**
```
rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101
```

**Dahua:**
```
rtsp://admin:password@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0
```

**Axis:**
```
rtsp://root:password@192.168.1.100/axis-media/media.amp
```

**Foscam:**
```
rtsp://admin:password@192.168.1.100:554/videoMain
```

## 🎯 Motion Detection Setup

1. Navigate to **Motion Settings**
2. Click on the canvas to add detection zones
3. Drag zones to reposition them
4. Press Delete key to remove selected zone
5. Adjust sensitivity, minimum area, and cooldown
6. Click **Save Settings**

### Tips for Motion Detection
- **Lower sensitivity (5-15)**: Detects small movements
- **Higher sensitivity (30-50)**: Only large movements
- **Min area (500-1000)**: Good for person detection
- **Cooldown (5-15s)**: Balance between responsiveness and bandwidth

## 📊 Monitoring

### Dashboard Features
- **Network Status**: Real-time upload speed graph
- **Active Streams**: Number of cameras streaming
- **Motion Activity**: Cameras with detected motion
- **Stream Cards**: Individual camera status

### Event Log
- View all motion events
- Timeline visualization
- Filter by camera
- Export logs

## 🔧 Troubleshooting

### GStreamer Not Found
**Linux:**
```bash
sudo apt-get install gstreamer1.0-tools gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

**Windows:**
Download from [gstreamer.freedesktop.org](https://gstreamer.freedesktop.org/download/)

### Camera Connection Failed
1. Verify RTSP URL is correct
2. Check camera username/password
3. Ensure camera is on same network
4. Test with VLC media player first
5. Check firewall settings

### High CPU Usage
1. Reduce resolution in `config.yaml`
2. Decrease motion detection frequency
3. Limit number of simultaneous streams
4. Use motion zones to reduce processing area

### Slow Network Warning
1. Check upload speed with speed test
2. Adjust `upload_speed_threshold_mbps` in config
3. Verify other bandwidth-consuming applications
4. Consider upgrading internet plan

## 📁 Project Structure

```
edge-agent-motion/
├── app.py                  # Main Flask application
├── streamer.py            # GStreamer streaming logic
├── motion_detector.py     # Motion detection
├── monitor.py             # Network monitoring
├── discovery.py           # ONVIF discovery
├── cloud_uploader.py      # Cloud chunk upload with auth
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── install.sh            # Linux installer
├── install.bat           # Windows installer
├── mock_cloud_server.py  # Testing server (optional)
├── logs/                 # Motion event logs & upload logs
│   ├── events_*.json     # Motion event data
│   └── cloud_upload.log  # Upload activity log
├── tmp/                  # Temporary storage
│   ├── chunks/           # Video chunks before upload
│   ├── buffer/           # Frame buffers
│   └── received/         # SRT received chunks
├── templates/            # HTML templates
│   ├── index.html
│   ├── discover.html
│   ├── add_manual.html
│   ├── motion.html
│   └── motion_log.html
└── static/
    └── js/
        └── dashboard.js  # Frontend JavaScript
```

## 🔐 Security Considerations

1. **Change default passwords**: Update camera credentials immediately
2. **Secure SRT passphrase**: Use strong encryption passphrase
3. **Network isolation**: Consider VLAN for cameras
4. **Web UI access**: Use firewall to restrict access
5. **HTTPS**: Consider reverse proxy with SSL for web UI

## 🚀 Performance Optimization

### For Low-End Devices (Raspberry Pi)
```yaml
normal_resolution: "640x360"
low_resolution: "480x270"
motion_high_fps: 15
```

### For High Performance
```yaml
normal_resolution: "1920x1080"
motion_high_fps: 30
motion_sensitivity: 20
```

## 📈 Bandwidth Savings

**Example Calculation:**
- **Normal streaming**: 25 FPS × 24/7 = Full bandwidth
- **Motion-triggered**: 1 FPS idle + 25 FPS during events
- **Typical savings**: 85-95% bandwidth reduction
- **10 cameras**: ~80-90% total bandwidth saved

## 🐛 Known Issues

1. **GStreamer pipeline warnings**: Normal, can be ignored if stream works
2. **First frame delay**: Expected ~2-3 seconds on startup
3. **Zone dragging on mobile**: Use desktop browser for zone configuration

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional camera protocols
- More sophisticated motion algorithms
- Cloud-side integration examples
- Mobile app
- Advanced analytics

## 📄 License

This project is provided as-is for educational and commercial use.

## 💡 Tips & Best Practices

1. **Test cameras individually** before adding multiple streams
2. **Start with default settings** and adjust based on results
3. **Monitor CPU usage** and adjust quality settings accordingly
4. **Use motion zones** to focus on important areas
5. **Regular log review** helps optimize sensitivity settings
6. **Backup config.yaml** before major changes

## 🆘 Support

For issues and questions:
1. Check this README thoroughly
2. Review logs in `logs/` directory
3. Test with VLC player to isolate camera issues
4. Verify GStreamer installation: `gst-launch-1.0 --version`

## 🎓 Technical Details

### Architecture
```
RTSP Camera → GStreamer Decode → OpenCV Motion Detection → 
Dynamic FPS Control → H.264 Encode → SRT Encrypt → Cloud Server
```

### Motion Detection Algorithm
- Frame differencing with Gaussian blur
- Contour detection
- Configurable sensitivity threshold
- Zone-based filtering
- Cooldown period for stability

### Network Adaptation
- Continuous upload speed monitoring
- Automatic quality switching
- Telegram notifications
- History tracking and visualization

---

**Built for developers, by developers** 🚀

Last updated: 2025