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