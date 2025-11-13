# Multi-stage build for smaller image
FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git make

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo \
    -ldflags="-w -s -X main.version=$(git describe --tags --always 2>/dev/null || echo 'dev') \
    -X main.buildTime=$(date -u '+%Y-%m-%d_%H:%M:%S') \
    -X main.gitCommit=$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
    -o /build/edge-agent ./cmd/agent

# Runtime stage
FROM alpine:3.19

RUN apk add --no-cache \
    ffmpeg \
    ca-certificates \
    tzdata

RUN addgroup -g 1000 edge && \
    adduser -D -u 1000 -G edge edge

RUN mkdir -p /etc/edge-agent/certs \
             /var/lib/edge-agent/buffer \
             /var/log/edge-agent && \
    chown -R edge:edge /var/lib/edge-agent /var/log/edge-agent

COPY --from=builder /build/edge-agent /usr/local/bin/

COPY configs/config.example.yaml /etc/edge-agent/config.yaml

USER edge

EXPOSE 8080 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

ENTRYPOINT ["/usr/local/bin/edge-agent"]
CMD ["-config", "/etc/edge-agent/config.yaml"]