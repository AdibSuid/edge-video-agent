package agent

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/yourorg/edge-video-agent/internal/alert"
	"github.com/yourorg/edge-video-agent/internal/camera"
	"github.com/yourorg/edge-video-agent/internal/config"
	"github.com/yourorg/edge-video-agent/internal/onvif"
	"github.com/yourorg/edge-video-agent/internal/stream"

	log "github.com/sirupsen/logrus"
)

type Agent struct {
	cfg       *config.Config
	alerter   *alert.TelegramAlerter
	discovery *onvif.Discovery

	registry       *camera.Registry
	streamManager  *stream.Manager
	healthMonitor  *HealthMonitor

	mu      sync.RWMutex
	running bool
	ctx     context.Context
	cancel  context.CancelFunc
}

func NewAgent(cfg *config.Config, alerter *alert.TelegramAlerter, discovery *onvif.Discovery) (*Agent, error) {
	registry, err := camera.NewRegistry()
	if err != nil {
		return nil, fmt.Errorf("failed to create camera registry: %w", err)
	}

	streamManager, err := stream.NewManager(cfg, alerter)
	if err != nil {
		return nil, fmt.Errorf("failed to create stream manager: %w", err)
	}

	healthMonitor := NewHealthMonitor(cfg, alerter)

	agent := &Agent{
		cfg:            cfg,
		alerter:        alerter,
		discovery:      discovery,
		registry:       registry,
		streamManager:  streamManager,
		healthMonitor:  healthMonitor,
	}

	return agent, nil
}

func (a *Agent) Start(ctx context.Context) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.running {
		return fmt.Errorf("agent already running")
	}

	a.ctx, a.cancel = context.WithCancel(ctx)
	a.running = true

	log.Info("Starting edge agent")

	if err := a.streamManager.Start(a.ctx); err != nil {
		return fmt.Errorf("failed to start stream manager: %w", err)
	}

	go a.healthMonitor.Start(a.ctx, a.registry, a.streamManager)
	go a.runPeriodicTasks(a.ctx)

	log.Info("Edge agent started successfully")
	return nil
}

func (a *Agent) Stop(ctx context.Context) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if !a.running {
		return nil
	}

	log.Info("Stopping edge agent")

	if a.cancel != nil {
		a.cancel()
	}

	stopCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	if err := a.streamManager.Stop(stopCtx); err != nil {
		log.Errorf("Error stopping stream manager: %v", err)
	}

	a.running = false
	log.Info("Edge agent stopped")
	return nil
}

func (a *Agent) AddCamera(cam camera.Camera) error {
	log.WithFields(log.Fields{
		"camera_id": cam.ID,
		"name":      cam.Name,
		"url":       cam.RTSPURL,
	}).Info("Adding camera")

	if err := a.registry.Add(cam); err != nil {
		return fmt.Errorf("failed to add camera to registry: %w", err)
	}

	if err := a.streamManager.StartStream(cam); err != nil {
		log.Warnf("Failed to start stream for camera %s: %v", cam.ID, err)
	}

	return nil
}

func (a *Agent) AddDiscoveredCamera(onvifCam onvif.Camera) error {
	cam := camera.Camera{
		ID:       onvifCam.UUID,
		Name:     onvifCam.Name,
		RTSPURL:  onvifCam.StreamURIs[0],
		Username: onvifCam.Username,
		Password: onvifCam.Password,
		Type:     "onvif",
		Metadata: map[string]string{
			"manufacturer": onvifCam.Manufacturer,
			"model":        onvifCam.Model,
			"firmware":     onvifCam.FirmwareVersion,
			"ip_address":   onvifCam.XAddr,
		},
	}

	if _, exists := a.registry.Get(cam.ID); exists {
		log.Debugf("Camera %s already exists, skipping", cam.ID)
		return nil
	}

	return a.AddCamera(cam)
}

func (a *Agent) RemoveCamera(cameraID string) error {
	log.WithField("camera_id", cameraID).Info("Removing camera")

	if err := a.streamManager.StopStream(cameraID); err != nil {
		log.Warnf("Failed to stop stream for camera %s: %v", cameraID, err)
	}

	if err := a.registry.Remove(cameraID); err != nil {
		return fmt.Errorf("failed to remove camera from registry: %w", err)
	}

	return nil
}

func (a *Agent) UpdateBitrate(cameraID string, bitrate int) error {
	return a.streamManager.UpdateBitrate(cameraID, bitrate)
}

func (a *Agent) GetCamera(cameraID string) (camera.Camera, error) {
	cam, exists := a.registry.Get(cameraID)
	if !exists {
		return camera.Camera{}, fmt.Errorf("camera not found: %s", cameraID)
	}
	return cam, nil
}

func (a *Agent) ListCameras() []camera.Camera {
	return a.registry.List()
}

func (a *Agent) GetStreamStatus(cameraID string) (stream.Status, error) {
	return a.streamManager.GetStatus(cameraID)
}

func (a *Agent) GetDiagnostics() map[string]interface{} {
	cameras := a.registry.List()
	activeStreams := 0

	for _, cam := range cameras {
		if status, err := a.streamManager.GetStatus(cam.ID); err == nil {
			if status.State == "running" {
				activeStreams++
			}
		}
	}

	return map[string]interface{}{
		"agent_id":        a.cfg.Agent.ID,
		"agent_name":      a.cfg.Agent.Name,
		"total_cameras":   len(cameras),
		"active_streams":  activeStreams,
		"uptime":          time.Since(a.healthMonitor.startTime).String(),
		"onvif_enabled":   a.cfg.ONVIF.Enabled,
		"adaptive_enabled": a.cfg.Adaptive.Enabled,
	}
}

func (a *Agent) runPeriodicTasks(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			a.performMaintenance()
		}
	}
}

func (a *Agent) performMaintenance() {
	cameras := a.registry.List()
	for _, cam := range cameras {
		status, err := a.streamManager.GetStatus(cam.ID)
		if err != nil {
			continue
		}

		if status.State == "failed" {
			log.WithField("camera_id", cam.ID).Info("Attempting to restart failed stream")
			if err := a.streamManager.StartStream(cam); err != nil {
				log.Warnf("Failed to restart stream for camera %s: %v", cam.ID, err)
			}
		}
	}
}