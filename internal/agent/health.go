package agent

import (
	"context"
	"time"

	"github.com/yourorg/edge-video-agent/internal/alert"
	"github.com/yourorg/edge-video-agent/internal/camera"
	"github.com/yourorg/edge-video-agent/internal/config"
	"github.com/yourorg/edge-video-agent/internal/stream"

	log "github.com/sirupsen/logrus"
)

type HealthMonitor struct {
	cfg       *config.Config
	alerter   *alert.TelegramAlerter
	startTime time.Time
	lastAlert map[string]time.Time
}

func NewHealthMonitor(cfg *config.Config, alerter *alert.TelegramAlerter) *HealthMonitor {
	return &HealthMonitor{
		cfg:       cfg,
		alerter:   alerter,
		startTime: time.Now(),
		lastAlert: make(map[string]time.Time),
	}
}

func (h *HealthMonitor) Start(ctx context.Context, registry *camera.Registry, manager *stream.Manager) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			h.checkHealth(registry, manager)
		}
	}
}

func (h *HealthMonitor) checkHealth(registry *camera.Registry, manager *stream.Manager) {
	cameras := registry.List()

	for _, cam := range cameras {
		status, err := manager.GetStatus(cam.ID)
		if err != nil {
			continue
		}

		if status.State == "failed" {
			h.sendAlertThrottled(
				cam.ID+"-failed",
				alert.AlertError,
				"Stream Failed",
				"Stream for camera "+cam.Name+" ("+cam.ID+") has failed",
			)
		}

		if status.ErrorCount > 10 {
			h.sendAlertThrottled(
				cam.ID+"-errors",
				alert.AlertWarning,
				"High Error Rate",
				"Camera "+cam.Name+" has experienced multiple errors",
			)
		}

		if status.CurrentBitrate > 0 && status.CurrentBitrate < status.TargetBitrate/2 {
			h.sendAlertThrottled(
				cam.ID+"-bitrate",
				alert.AlertWarning,
				"Low Bitrate",
				"Camera "+cam.Name+" bitrate has dropped significantly",
			)
		}
	}
}

func (h *HealthMonitor) sendAlertThrottled(key string, level alert.AlertLevel, title, message string) {
	if h.alerter == nil {
		return
	}

	if lastTime, exists := h.lastAlert[key]; exists {
		if time.Since(lastTime) < 5*time.Minute {
			return
		}
	}

	if err := h.alerter.SendAlert(level, title, message); err != nil {
		log.Warnf("Failed to send alert: %v", err)
	}

	h.lastAlert[key] = time.Now()
}