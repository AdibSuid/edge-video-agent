package stream

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/yourorg/edge-video-agent/internal/alert"
	"github.com/yourorg/edge-video-agent/internal/camera"
	"github.com/yourorg/edge-video-agent/internal/config"

	log "github.com/sirupsen/logrus"
)

type Status struct {
	CameraID       string    `json:"camera_id"`
	State          string    `json:"state"`
	StartedAt      time.Time `json:"started_at"`
	LastError      string    `json:"last_error,omitempty"`
	ErrorCount     int       `json:"error_count"`
	CurrentBitrate int       `json:"current_bitrate"`
	TargetBitrate  int       `json:"target_bitrate"`
	CurrentFPS     int       `json:"current_fps"`
	Resolution     string    `json:"resolution"`
	BytesSent      int64     `json:"bytes_sent"`
	PacketsLost    int64     `json:"packets_lost"`
}

type Manager struct {
	cfg     *config.Config
	alerter *alert.TelegramAlerter

	mu      sync.RWMutex
	streams map[string]*Stream
	ctx     context.Context
	cancel  context.CancelFunc
}

func NewManager(cfg *config.Config, alerter *alert.TelegramAlerter) (*Manager, error) {
	return &Manager{
		cfg:     cfg,
		alerter: alerter,
		streams: make(map[string]*Stream),
	}, nil
}

func (m *Manager) Start(ctx context.Context) error {
	m.ctx, m.cancel = context.WithCancel(ctx)
	log.Info("Stream manager started")
	return nil
}

func (m *Manager) Stop(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	log.Info("Stopping stream manager")

	var wg sync.WaitGroup
	for _, stream := range m.streams {
		wg.Add(1)
		go func(s *Stream) {
			defer wg.Done()
			if err := s.Stop(ctx); err != nil {
				log.Errorf("Error stopping stream %s: %v", s.cameraID, err)
			}
		}(stream)
	}

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		log.Info("All streams stopped")
	case <-ctx.Done():
		log.Warn("Stop timeout reached, some streams may not have stopped gracefully")
	}

	return nil
}

func (m *Manager) StartStream(cam camera.Camera) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, exists := m.streams[cam.ID]; exists {
		return fmt.Errorf("stream already exists for camera %s", cam.ID)
	}

	log.WithFields(log.Fields{
		"camera_id": cam.ID,
		"name":      cam.Name,
	}).Info("Starting stream")

	stream, err := NewStream(cam, m.cfg, m.alerter)
	if err != nil {
		return fmt.Errorf("failed to create stream: %w", err)
	}

	if err := stream.Start(m.ctx); err != nil {
		return fmt.Errorf("failed to start stream: %w", err)
	}

	m.streams[cam.ID] = stream
	return nil
}

func (m *Manager) StopStream(cameraID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	stream, exists := m.streams[cameraID]
	if !exists {
		return fmt.Errorf("stream not found for camera %s", cameraID)
	}

	log.WithField("camera_id", cameraID).Info("Stopping stream")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := stream.Stop(ctx); err != nil {
		return fmt.Errorf("failed to stop stream: %w", err)
	}

	delete(m.streams, cameraID)
	return nil
}

func (m *Manager) GetStatus(cameraID string) (Status, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	stream, exists := m.streams[cameraID]
	if !exists {
		return Status{}, fmt.Errorf("stream not found for camera %s", cameraID)
	}

	return stream.GetStatus(), nil
}

func (m *Manager) UpdateBitrate(cameraID string, bitrate int) error {
	m.mu.RLock()
	stream, exists := m.streams[cameraID]
	m.mu.RUnlock()

	if !exists {
		return fmt.Errorf("stream not found for camera %s", cameraID)
	}

	return stream.UpdateBitrate(bitrate)
}

func (m *Manager) ListStreams() []Status {
	m.mu.RLock()
	defer m.mu.RUnlock()

	statuses := make([]Status, 0, len(m.streams))
	for _, stream := range m.streams {
		statuses = append(statuses, stream.GetStatus())
	}

	return statuses
}