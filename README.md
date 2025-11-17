<<<<<<< HEAD
# Edge Video Agent

Industrial-grade edge agent for IP camera discovery, video streaming, and cloud integration.

## 🎯 Features

- **ONVIF Camera Discovery**: Automatic IP camera detection via WS-Discovery
- **Multi-Protocol Support**: RTSP, RTSPS, HTTP camera sources
- **Secure Streaming**: SRT (Secure Reliable Transport) with AES encryption
- **Adaptive Bitrate**: Automatic quality adjustment based on network conditions
- **CPU-Only Encoding**: FFmpeg with libx264 (no GPU required)
- **Cloud Control**: gRPC with mutual TLS for secure command & control
- **Resilient**: Auto-reconnect, buffering, and graceful degradation
- **Alerting**: Telegram notifications for connectivity issues
- **Cross-Platform**: Runs on Linux/Windows, x86/ARM

## 🚀 Quick Start

### Docker (Fastest)
```bash
git clone https://github.com/yourorg/edge-video-agent
cd edge-video-agent
cp configs/config.example.yaml configs/config.yaml
# Edit configs/config.yaml with your settings
docker-compose up -d
```

### Build from Source
```bash
./scripts/dev-setup.sh
make build
./bin/edge-agent -config configs/config.yaml
```

### Production Deployment
```bash
make build
sudo make install-service
sudo systemctl enable edge-agent
sudo systemctl start edge-agent
```

## 📋 Configuration

Minimal `configs/config.yaml`:
```yaml
agent:
  id: "edge-001"
  name: "Building A - Floor 1"

cloud:
  srt_endpoint: "srt://cloud.example.com:9000"
  srt_passphrase: "your-secure-passphrase"
  grpc_endpoint: "cloud.example.com:50051"

onvif:
  enabled: true
```

See `configs/config.example.yaml` for all options.

## 📚 Documentation

- [Quick Start Guide](docs/QUICKSTART.md)
- [Architecture Documentation](docs/ARCHITECTURE.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## 🔧 Development
```bash
make build          # Build binary
make test           # Run tests
make lint           # Run linter
make docker-build   # Build Docker image
make help           # Show all commands
```

## 📊 Monitoring

- **Metrics**: http://localhost:8080/metrics (Prometheus)
- **Health**: http://localhost:8080/health
- **gRPC**: localhost:50051

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 License

MIT License - See [LICENSE](LICENSE)

## 🙏 Acknowledgments

Architecture based on industry standards from Hikvision, Milestone, AWS Panorama, and professional VMS systems.
=======
# Edge Agent - Motion-Triggered Video Streaming

A lightweight edge video surveillance agent that converts local CCTV streams to secure, cloud-ready video feeds with intelligent bandwidth optimization through motion detection.

## 🎯 Key Features

- **ONVIF Discovery**: Automatically find IP cameras on your network
- **Manual RTSP Addition**: Add any RTSP-compatible camera manually
- **Motion-Triggered Adaptive FPS**: 
  - **Idle**: 1 FPS (saves ~90% bandwidth)
  - **Motion**: 25 FPS (full quality)
- **Secure Streaming**: AES-256 encrypted SRT streaming to cloud
- **Network Monitoring**: Real-time upload speed tracking
- **Adaptive Quality**: Automatic resolution reduction on slow connections
- **Telegram Alerts**: Get notified of connectivity issues
- **Web UI**: Easy-to-use browser interface
- **Draggable Motion Zones**: Define specific areas for motion detection
- **Event Logging**: Track all motion events with timeline visualization
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

## 📱 Telegram Setup (Optional)

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add credentials to `config.yaml`

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
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── install.sh            # Linux installer
├── install.bat           # Windows installer
├── logs/                 # Motion event logs
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
>>>>>>> master
