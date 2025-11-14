package stream

import (
	"bufio"
	"io"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/yourorg/edge-video-agent/internal/alert"
	"github.com/yourorg/edge-video-agent/internal/camera"
	"github.com/yourorg/edge-video-agent/internal/config"

	log "github.com/sirupsen/logrus"
)

type Stream struct {
	camera  camera.Camera
	cfg     *config.Config
	alerter *alert.TelegramAlerter

	mu              sync.RWMutex
	cameraID        string
	state           string
	cmd             *exec.Cmd
	ctx             context.Context
	cancel          context.CancelFunc
	startedAt       time.Time
	lastError       string
	errorCount      int
	currentBitrate  int
	targetBitrate   int
	currentFPS      int
	resolution      string
	bytesSent       int64
	packetsLost     int64
	bitrateProfile  config.BitrateProfile
	adaptiveMonitor *AdaptiveMonitor
}

func NewStream(cam camera.Camera, cfg *config.Config, alerter *alert.TelegramAlerter) (*Stream, error) {
	profile := cfg.Adaptive.Bitrateladder[len(cfg.Adaptive.Bitrateladder)/2]

	stream := &Stream{
		camera:         cam,
		cfg:            cfg,
		alerter:        alerter,
		cameraID:       cam.ID,
		state:          "stopped",
		targetBitrate:  profile.Bitrate,
		currentBitrate: profile.Bitrate,
		currentFPS:     profile.FPS,
		resolution:     profile.Resolution,
		bitrateProfile: profile,
	}

	if cfg.Adaptive.Enabled {
		stream.adaptiveMonitor = NewAdaptiveMonitor(cfg, stream)
	}

	return stream, nil
}

func (s *Stream) Start(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.state == "running" {
		return fmt.Errorf("stream already running")
	}

	s.ctx, s.cancel = context.WithCancel(ctx)
	s.state = "starting"
	s.startedAt = time.Now()

	args := s.buildFFmpegArgs()
	s.cmd = exec.CommandContext(s.ctx, "ffmpeg", args...)

	stderr, err := s.cmd.StderrPipe()
	if err != nil {
		s.state = "failed"
		s.lastError = err.Error()
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	if err := s.cmd.Start(); err != nil {
		s.state = "failed"
		s.lastError = err.Error()
		return fmt.Errorf("failed to start ffmpeg: %w", err)
	}

	s.state = "running"

	log.WithFields(log.Fields{
		"camera_id":  s.cameraID,
		"bitrate":    s.currentBitrate,
		"fps":        s.currentFPS,
		"resolution": s.resolution,
	}).Info("Stream started")

	go s.monitorFFmpeg(stderr)

	if s.adaptiveMonitor != nil {
		go s.adaptiveMonitor.Start(s.ctx)
	}

	go s.monitorProcess()

	return nil
}

func (s *Stream) Stop(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.state == "stopped" || s.state == "stopping" {
		return nil
	}

	log.WithField("camera_id", s.cameraID).Info("Stopping stream")

	s.state = "stopping"

	if s.cancel != nil {
		s.cancel()
	}

	if s.cmd != nil && s.cmd.Process != nil {
		done := make(chan error, 1)
		go func() {
			done <- s.cmd.Wait()
		}()

		select {
		case <-done:
			log.WithField("camera_id", s.cameraID).Debug("Stream stopped gracefully")
		case <-ctx.Done():
			log.WithField("camera_id", s.cameraID).Warn("Stop timeout, killing process")
			if err := s.cmd.Process.Kill(); err != nil {
				log.Errorf("Failed to kill process: %v", err)
			}
		}
	}

	s.state = "stopped"
	return nil
}

func (s *Stream) buildFFmpegArgs() []string {
	args := []string{
		"-rtsp_transport", "tcp",
		"-i", s.buildInputURL(),
		"-c:v", "libx264",
		"-preset", s.cfg.Encoding.Preset,
		"-tune", s.cfg.Encoding.Tune,
		"-b:v", fmt.Sprintf("%d", s.currentBitrate),
		"-maxrate", fmt.Sprintf("%d", s.currentBitrate),
		"-bufsize", fmt.Sprintf("%d", s.currentBitrate*2),
		"-r", fmt.Sprintf("%d", s.currentFPS),
		"-g", fmt.Sprintf("%d", s.cfg.Encoding.GOPSize),
	}

	if s.resolution != "" {
		args = append(args, "-s", s.resolution)
	}

	args = append(args, "-an")
	args = append(args,
		"-f", "mpegts",
		"-flush_packets", "1",
	)

	srtURL := s.buildSRTURL()
	args = append(args, srtURL)

	args = append(args,
		"-reconnect", "1",
		"-reconnect_streamed", "1",
		"-reconnect_delay_max", "5",
	)

	return args
}

func (s *Stream) buildInputURL() string {
	url := s.camera.RTSPURL

	if s.camera.Username != "" && s.camera.Password != "" {
		parts := strings.SplitN(url, "://", 2)
		if len(parts) == 2 {
			url = fmt.Sprintf("%s://%s:%s@%s", parts[0], s.camera.Username, s.camera.Password, parts[1])
		}
	}

	return url
}

func (s *Stream) buildSRTURL() string {
	endpoint := s.cfg.Cloud.SRTEndpoint
	passphrase := s.cfg.Cloud.SRTPassphrase
	latency := s.cfg.Cloud.SRTLatency

	// If the endpoint is a local file URL, don't append SRT params — FFmpeg
	// expects a plain file path for file output. For SRT endpoints we append
	// the necessary SRT connection parameters.
	if strings.HasPrefix(endpoint, "file:") {
		return endpoint
	}

	params := fmt.Sprintf("?mode=caller&latency=%d&pbkeylen=16&passphrase=%s&streamid=%s",
		latency, passphrase, s.cameraID)

	return endpoint + params
}

func (s *Stream) monitorFFmpeg(stderr io.Reader) {
	scanner := bufio.NewScanner(stderr)
	for scanner.Scan() {
		line := scanner.Text()

		log.WithFields(log.Fields{
			"camera_id": s.cameraID,
			"output":    line,
		}).Trace("FFmpeg output")

		if strings.Contains(line, "error") || strings.Contains(line, "Error") {
			s.mu.Lock()
			s.errorCount++
			s.lastError = line
			s.mu.Unlock()

			log.WithFields(log.Fields{
				"camera_id": s.cameraID,
				"error":     line,
			}).Warn("FFmpeg error detected")
		}

		s.parseFFmpegStats(line)
	}
}

func (s *Stream) parseFFmpegStats(line string) {
	if strings.Contains(line, "frame=") && strings.Contains(line, "bitrate=") {
		if idx := strings.Index(line, "bitrate="); idx != -1 {
			bitrateStr := line[idx+8:]
			var bitrate float64
			fmt.Sscanf(bitrateStr, "%fkbits/s", &bitrate)

			s.mu.Lock()
			s.currentBitrate = int(bitrate * 1000)
			s.mu.Unlock()
		}

		if idx := strings.Index(line, "fps="); idx != -1 {
			fpsStr := line[idx+4:]
			var fps int
			fmt.Sscanf(fpsStr, "%d", &fps)

			s.mu.Lock()
			s.currentFPS = fps
			s.mu.Unlock()
		}
	}
}

func (s *Stream) monitorProcess() {
	err := s.cmd.Wait()

	s.mu.Lock()
	defer s.mu.Unlock()

	if err != nil && s.state != "stopping" {
		s.state = "failed"
		s.lastError = err.Error()
		s.errorCount++

		log.WithFields(log.Fields{
			"camera_id": s.cameraID,
			"error":     err,
		}).Error("Stream process failed")

		if s.alerter != nil {
			s.alerter.SendAlert(
				alert.AlertError,
				"Stream Failed",
				fmt.Sprintf("Stream for camera %s failed: %v", s.cameraID, err),
			)
		}
	} else if s.state != "stopping" {
		s.state = "stopped"
	}
}

func (s *Stream) UpdateBitrate(bitrate int) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	log.WithFields(log.Fields{
		"camera_id":     s.cameraID,
		"old_bitrate":   s.targetBitrate,
		"new_bitrate":   bitrate,
	}).Info("Updating stream bitrate")

	s.targetBitrate = bitrate
	return nil
}

func (s *Stream) GetStatus() Status {
	s.mu.RLock()
	defer s.mu.RUnlock()

	return Status{
		CameraID:       s.cameraID,
		State:          s.state,
		StartedAt:      s.startedAt,
		LastError:      s.lastError,
		ErrorCount:     s.errorCount,
		CurrentBitrate: s.currentBitrate,
		TargetBitrate:  s.targetBitrate,
		CurrentFPS:     s.currentFPS,
		Resolution:     s.resolution,
		BytesSent:      s.bytesSent,
		PacketsLost:    s.packetsLost,
	}
}