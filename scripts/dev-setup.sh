#!/bin/bash
set -e

echo "Edge Video Agent - Development Setup"
echo "====================================="

echo ""
echo "Checking prerequisites..."

if ! command -v go &> /dev/null; then
    echo "❌ Go not found. Please install Go 1.21 or later."
    exit 1
fi
echo "✅ Go $(go version | awk '{print $3}')"

if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found. Installing..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y ffmpeg
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install ffmpeg
    fi
else
    echo "✅ FFmpeg $(ffmpeg -version | head -n1 | awk '{print $3}')"
fi

if ! command -v make &> /dev/null; then
    echo "⚠️  Make not found. Install it for build automation."
else
    echo "✅ Make"
fi

echo ""
echo "Installing Go development tools..."

if ! command -v protoc &> /dev/null; then
    echo "⚠️  protoc not found. Install it to regenerate gRPC code."
    echo "   Download from: https://github.com/protocolbuffers/protobuf/releases"
else
    echo "✅ protoc"
fi

echo "Installing Go protobuf plugins..."
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

echo "Installing golangci-lint..."
if ! command -v golangci-lint &> /dev/null; then
    curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin
fi
echo "✅ golangci-lint"

echo "Installing air for live reload (optional)..."
go install github.com/cosmtrek/air@latest

echo "Installing grpcurl for gRPC testing (optional)..."
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest

echo ""
echo "Downloading Go dependencies..."
go mod download
go mod tidy

echo ""
echo "Creating development directories..."
mkdir -p bin
mkdir -p tmp
mkdir -p configs
mkdir -p certs

if [ ! -f "configs/config.yaml" ]; then
    echo "Creating default configuration..."
    cp configs/config.example.yaml configs/config.yaml
    echo "⚠️  Edit configs/config.yaml with your settings"
fi

cat > .env.example << 'EOF'
# Agent Configuration
AGENT_ID=dev-edge-001
AGENT_NAME=Development Edge Agent

# Cloud Endpoints
SRT_ENDPOINT=srt://localhost:9000
SRT_PASSPHRASE=dev-passphrase-change-me
GRPC_ENDPOINT=localhost:50051

# Telegram (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF

echo "✅ Created .env.example"

cat > .air.toml << 'EOF'
root = "."
testdata_dir = "testdata"
tmp_dir = "tmp"

[build]
  args_bin = ["-config", "configs/config.yaml"]
  bin = "./tmp/edge-agent"
  cmd = "go build -o ./tmp/edge-agent ./cmd/agent"
  delay = 1000
  exclude_dir = ["assets", "tmp", "vendor", "testdata", "bin"]
  exclude_file = []
  exclude_regex = ["_test.go"]
  exclude_unchanged = false
  follow_symlink = false
  full_bin = ""
  include_dir = []
  include_ext = ["go", "tpl", "tmpl", "html", "yaml"]
  include_file = []
  kill_delay = "0s"
  log = "build-errors.log"
  poll = false
  poll_interval = 0
  rerun = false
  rerun_delay = 500
  send_interrupt = false
  stop_on_error = false

[color]
  app = ""
  build = "yellow"
  main = "magenta"
  runner = "green"
  watcher = "cyan"

[log]
  main_only = false
  time = false

[misc]
  clean_on_exit = false

[screen]
  clear_on_rebuild = false
  keep_scroll = true
EOF

echo "✅ Created .air.toml for live reload"

echo ""
echo "Building project..."
go build -o bin/edge-agent ./cmd/agent

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit configs/config.yaml with your settings"
echo "  2. Run: make run          # Build and run"
echo "  3. Run: make dev          # Run with live reload"
echo "  4. Run: make test         # Run tests"
echo "  5. Run: make docker-run   # Run in Docker"
echo ""
echo "Development commands:"
echo "  make build       - Build binary"
echo "  make test        - Run tests"
echo "  make lint        - Run linter"
echo "  make proto       - Generate protobuf code"
echo "  make help        - Show all commands"
echo ""
echo "Happy coding! 🚀"
```

### 23. `.gitignore`
```
# Binaries
bin/
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test binary
*.test

# Coverage
*.out
coverage.html

# Go workspace
go.work

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Configuration
config.yaml
configs/config.yaml
*.key
*.crt
*.pem

# Logs
*.log
logs/

# Buffer
buffer/
tmp/

# Build artifacts
dist/
release/

# Docker
.docker/

# Environment
.env
.env.local
```

### 24. `LICENSE`
```
MIT License

Copyright (c) 2024 Edge Video Agent Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.