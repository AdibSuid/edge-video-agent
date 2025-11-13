.PHONY: all build test clean docker-build docker-push install-service proto lint help

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME ?= $(shell date -u '+%Y-%m-%d_%H:%M:%S')
GIT_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null || echo "unknown")
BINARY_NAME = edge-agent
DOCKER_IMAGE = edge-video-agent
DOCKER_TAG ?= latest

GOCMD = go
GOBUILD = $(GOCMD) build
GOTEST = $(GOCMD) test
GOGET = $(GOCMD) get
GOMOD = $(GOCMD) mod
LDFLAGS = -ldflags="-w -s -X main.version=$(VERSION) -X main.buildTime=$(BUILD_TIME) -X main.gitCommit=$(GIT_COMMIT)"

BUILD_DIR = bin
OUTPUT = $(BUILD_DIR)/$(BINARY_NAME)

all: clean build

build:
	@echo "Building $(BINARY_NAME) version $(VERSION)..."
	@mkdir -p $(BUILD_DIR)
	$(GOBUILD) $(LDFLAGS) -o $(OUTPUT) ./cmd/agent
	@echo "Build complete: $(OUTPUT)"

build-linux:
	@echo "Building for Linux..."
	@mkdir -p $(BUILD_DIR)
	GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-linux-amd64 ./cmd/agent
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)-linux-amd64"

build-windows:
	@echo "Building for Windows..."
	@mkdir -p $(BUILD_DIR)
	GOOS=windows GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-windows-amd64.exe ./cmd/agent
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)-windows-amd64.exe"

build-arm:
	@echo "Building for ARM..."
	@mkdir -p $(BUILD_DIR)
	GOOS=linux GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME)-linux-arm64 ./cmd/agent
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)-linux-arm64"

test:
	@echo "Running tests..."
	$(GOTEST) -v -race -coverprofile=coverage.out ./...
	@echo "Tests complete"

test-coverage: test
	@echo "Generating coverage report..."
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

lint:
	@echo "Running linter..."
	@which golangci-lint > /dev/null || (echo "golangci-lint not installed" && exit 1)
	golangci-lint run --timeout 5m
	@echo "Linting complete"

proto:
	@echo "Generating protobuf code..."
	@which protoc > /dev/null || (echo "protoc not installed" && exit 1)
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		api/proto/*.proto
	@echo "Protobuf generation complete"

docker-build:
	@echo "Building Docker image $(DOCKER_IMAGE):$(DOCKER_TAG)..."
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "Docker image built: $(DOCKER_IMAGE):$(DOCKER_TAG)"

docker-push:
	@echo "Pushing Docker image $(DOCKER_IMAGE):$(DOCKER_TAG)..."
	docker push $(DOCKER_IMAGE):$(DOCKER_TAG)
	@echo "Docker image pushed"

docker-run:
	@echo "Running Docker container..."
	docker-compose up -d
	@echo "Container started. Check logs with: docker-compose logs -f"

docker-stop:
	@echo "Stopping Docker container..."
	docker-compose down
	@echo "Container stopped"

install-service: build
	@echo "Installing systemd service..."
	@sudo cp $(OUTPUT) /usr/local/bin/
	@sudo cp deployments/systemd/edge-agent.service /etc/systemd/system/
	@sudo systemctl daemon-reload
	@echo "Service installed. Enable with: sudo systemctl enable edge-agent"

clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out coverage.html
	@echo "Clean complete"

deps:
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) tidy
	@echo "Dependencies downloaded"

run: build
	@echo "Running $(BINARY_NAME)..."
	$(OUTPUT) -config configs/config.yaml

dev:
	@echo "Running in development mode..."
	@which air > /dev/null || (echo "air not installed, run: go install github.com/cosmtrek/air@latest" && exit 1)
	air

help:
	@echo "Edge Video Agent - Makefile Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""