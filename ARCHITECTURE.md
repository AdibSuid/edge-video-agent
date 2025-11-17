# Edge Agent Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Edge Agent (Local)                       │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │   Web UI   │  │   Monitor    │  │   Motion Detector   │ │
│  │  (Flask)   │  │  (Network)   │  │     (OpenCV)        │ │
│  └────────────┘  └──────────────┘  └─────────────────────┘ │
│         │                │                      │            │
│         └────────────────┴──────────────────────┘            │
│                          │                                   │
│              ┌───────────▼──────────┐                        │
│              │   Streamer Manager   │                        │
│              └───────────┬──────────┘                        │
│                          │                                   │
│         ┌────────────────┼────────────────┐                 │
│         │                │                │                 │
│    ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐          │
│    │ Stream 1 │    │ Stream 2 │    │ Stream N │          │
│    │ (GStream)│    │ (GStream)│    │ (GStream)│          │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘          │
│         │                │                │                 │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                    SRT (Encrypted)
                           │
                           ▼
            ┌──────────────────────────┐
            │   Cloud GPU Server        │
            │  - DeepStream            │
            │  - Triton Inference      │
            │  - WebRTC Viewer         │
            └──────────────────────────┘
```

## Component Details

### 1. Flask Web Application (`app.py`)
**Purpose**: Web-based user interface and API server

**Responsibilities:**
- Serve HTML dashboard
- Handle API requests
- Manage configuration
- Coordinate background services

**Key Routes:**
- `/` - Main dashboard
- `/discover` - ONVIF camera discovery
- `/add_manual` - Manual camera addition
- `/motion` - Motion settings
- `/motion_log` - Event viewer
- `/api/*` - RESTful API endpoints

**Technologies:**
- Flask 3.0
- Bootstrap 5.3
- Chart.js 4.4

### 2. Streamer (`streamer.py`)
**Purpose**: Handle video streaming with motion-triggered FPS

**Flow:**
```
RTSP Input → Decode → Motion Analysis → FPS Control → 
Encode → SRT Encrypt → Cloud
```

**Key Features:**
- GStreamer pipeline management
- Dynamic FPS switching (1 → 25)
- Resolution adaptation
- Auto-restart on failure
- Multi-stream support

**GStreamer Pipeline:**
```
rtspsrc → rtph264depay → h264parse → avdec_h264 →
videoconvert → videoscale → videorate → x264enc →
mpegtsmux → srtsink
```

### 3. Motion Detector (`motion_detector.py`)
**Purpose**: CPU-only motion detection using OpenCV

**Algorithm:**
1. Convert frame to grayscale
2. Apply Gaussian blur
3. Compute frame difference
4. Threshold binary image
5. Find contours
6. Filter by zone and size
7. Trigger on significant motion

**Performance:**
- CPU usage: 8-15% on 720p
- Latency: <100ms
- Memory: ~50MB per stream

**Configurable Parameters:**
- Sensitivity (threshold)
- Minimum area
- Detection zones
- Cooldown period

### 4. Network Monitor (`monitor.py`)
**Purpose**: Track upload speed and trigger quality adaptation

**Monitoring Process:**
```python
while True:
    current_bytes = get_network_bytes_sent()
    speed_mbps = calculate_speed(current_bytes, previous_bytes)
    
    if speed_mbps < threshold:
        trigger_low_quality_mode()
        send_telegram_alert()
    
    update_history(speed_mbps)
    sleep(5_seconds)
```

**Features:**
- Real-time speed calculation
- 5-minute history tracking
- Threshold-based alerts
- Telegram integration

### 5. ONVIF Discovery (`discovery.py`)
**Purpose**: Discover and manage IP cameras

**Discovery Methods:**
1. **WS-Discovery**: Multicast probe on 239.255.255.250:3702
2. **Port Scan**: TCP scan for common camera ports
3. **ONVIF Protocol**: Query device information

**Supported Operations:**
- Discover cameras
- Get device info
- List stream profiles
- Extract RTSP URLs
- Test connectivity

## Data Flow

### Motion Detection Flow
```
Camera → RTSP Stream → CV2 Capture (30fps) → Queue
                                               ↓
                              Motion Detector ← Frame
                                               ↓
                                    [Motion Detected?]
                                     ↙            ↘
                                   Yes            No
                                    ↓              ↓
                             Set 25fps      Keep 1fps
                                    ↓              ↓
                          Restart Pipeline  Continue
```

### Network Adaptation Flow
```
Monitor Upload Speed (5s intervals)
        ↓
   Speed < Threshold?
        ↓
      Yes → Switch to Low Quality (640×360)
        ↓
   Send Telegram Alert
        ↓
   Continue Monitoring
        ↓
   Speed Recovered?
        ↓
      Yes → Switch to Normal Quality (1280×720)
        ↓
   Send Recovery Alert
```

### Configuration Flow
```
config.yaml → load_config() → Global Config
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
              Web UI Updates   Streamer Reads   Monitor Reads
                    ↓               ↓               ↓
            save_config() ← restart_services() → apply_settings()
```

## File Structure

```
edge-agent-motion/
│
├── Core Application
│   ├── app.py                 # Flask web server (500 lines)
│   ├── streamer.py           # GStreamer manager (300 lines)
│   ├── motion_detector.py    # Motion detection (150 lines)
│   ├── monitor.py            # Network monitoring (200 lines)
│   └── discovery.py          # ONVIF discovery (250 lines)
│
├── Configuration
│   ├── config.yaml           # Main configuration
│   └── requirements.txt      # Python dependencies
│
├── Web Interface
│   ├── templates/
│   │   ├── index.html       # Dashboard (200 lines)
│   │   ├── discover.html    # Discovery page (150 lines)
│   │   ├── add_manual.html  # Manual add (120 lines)
│   │   ├── motion.html      # Motion config (180 lines)
│   │   └── motion_log.html  # Event log (120 lines)
│   │
│   └── static/
│       └── js/
│           └── dashboard.js  # Frontend logic (150 lines)
│
├── Installation
│   ├── install.sh           # Linux installer
│   ├── install.bat          # Windows installer
│   └── QUICK_START.md       # Setup guide
│
├── Documentation
│   ├── README.md            # Main documentation
│   ├── ARCHITECTURE.md      # This file
│   └── .gitignore          # Git ignore rules
│
└── Runtime Data
    ├── logs/                # Motion event logs
    │   ├── motion_cam1.log
    │   └── events_cam1.json
    └── venv/                # Python virtual environment
```

## Performance Characteristics

### CPU Usage (per stream)
| Resolution | Idle (1fps) | Motion (25fps) | Motion Detection |
|-----------|-------------|----------------|------------------|
| 640×360   | ~2%         | ~8%            | ~2%              |
| 1280×720  | ~3%         | ~15%           | ~5%              |
| 1920×1080 | ~5%         | ~25%           | ~8%              |

### Memory Usage
- Base application: ~100MB
- Per stream: ~50MB
- OpenCV overhead: ~30MB per stream

### Network Bandwidth (per stream)
| Mode      | Resolution | FPS | Bitrate      | Daily Transfer |
|-----------|-----------|-----|--------------|----------------|
| Idle      | 1280×720  | 1   | ~30 kbps     | ~320 MB        |
| Motion    | 1280×720  | 25  | ~800 kbps    | ~8.5 GB        |
| Typical   | 1280×720  | Mix | ~100-200 kbps| ~1-2 GB        |

### Bandwidth Savings
- **Without motion**: 100% of time at 25fps = 8.5 GB/day
- **With motion** (10% active): 90% at 1fps + 10% at 25fps = ~1.2 GB/day
- **Savings**: ~86% bandwidth reduction

## Security Considerations

### Encryption
- **SRT Protocol**: AES-128/256 encryption
- **Passphrase**: User-configured, 16+ characters recommended
- **Transport**: UDP with built-in encryption

### Network Security
```
Camera (LAN) → Edge Agent (LAN) → SRT Tunnel → Cloud (WAN)
  Private         Private          Encrypted      Public
```

### Recommendations
1. **Isolate cameras**: Use VLAN for camera network
2. **Change defaults**: Update all camera passwords
3. **Firewall rules**: Restrict web UI access
4. **HTTPS**: Use reverse proxy (nginx) for SSL
5. **Strong passphrases**: 20+ character SRT passphrase

## Scalability

### Single Edge Agent
- **Max streams**: 10-15 (depends on CPU)
- **Max resolution**: 1080p per stream
- **Bandwidth**: 5-10 Mbps upload typical

### Multiple Edge Agents
```
Location A (Edge Agent 1) ─┐
                            ├─→ Cloud Server
Location B (Edge Agent 2) ─┘
```

Each agent handles its own cameras independently.

## Extension Points

### Adding New Features

1. **New Camera Protocol**
   - Extend `discovery.py`
   - Add protocol handler
   - Update UI

2. **Advanced Motion Algorithms**
   - Modify `motion_detector.py`
   - Add ML model integration
   - Keep CPU-only option

3. **Cloud Integration**
   - Extend API in `app.py`
   - Add cloud sync module
   - Implement callbacks

4. **Mobile App**
   - Use existing API endpoints
   - WebSocket for real-time
   - React Native recommended

## Dependencies

### System (Linux)
- GStreamer 1.0+ with plugins
- Python 3.8+
- OpenCV 4.0+
- Network tools (ifconfig, etc.)

### Python Packages
```
Flask==3.0.0          # Web framework
PyYAML==6.0.1         # Config parsing
opencv-python==4.8.1  # Computer vision
numpy==1.24.3         # Numerical operations
requests==2.31.0      # HTTP client
onvif-zeep==0.2.12    # ONVIF protocol
python-telegram-bot   # Telegram integration
psutil==5.9.6         # System monitoring
```

### Optional
- Redis (for multi-agent coordination)
- PostgreSQL (for event storage)
- Docker (for containerization)

## Testing

### Unit Tests
```bash
pytest tests/test_motion_detector.py
pytest tests/test_monitor.py
pytest tests/test_discovery.py
```

### Integration Tests
```bash
pytest tests/test_streaming_pipeline.py
pytest tests/test_api_endpoints.py
```

### Performance Tests
```bash
python tests/benchmark_motion.py
python tests/benchmark_streaming.py
```

## Monitoring & Logging

### Log Files
- `logs/motion_<stream_id>.log` - Motion events
- `logs/events_<stream_id>.json` - Structured events
- Application logs to stdout

### Metrics Available
- Upload speed (Mbps)
- FPS per stream
- CPU usage
- Memory usage
- Motion events
- Stream uptime

## Future Roadmap

1. **Phase 1** (Current)
   - ✅ Basic streaming
   - ✅ Motion detection
   - ✅ Web UI

2. **Phase 2**
   - Docker support
   - Cloud dashboard
   - Multi-agent management

3. **Phase 3**
   - AI object detection
   - Face recognition
   - Advanced analytics

4. **Phase 4**
   - Mobile app
   - Cloud recording
   - Event replay

---

**Last Updated**: 2025
**Version**: 1.0