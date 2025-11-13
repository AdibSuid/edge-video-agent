package stream

import (
	"context"
	"time"

	"github.com/yourorg/edge-video-agent/internal/config"

	log "github.com/sirupsen/logrus"
)

type AdaptiveMonitor struct {
	cfg    *config.Config
	stream *Stream

	ewmaThroughput float64
	alpha          float64
	measurements   []int64
}

func NewAdaptiveMonitor(cfg *config.Config, stream *Stream) *AdaptiveMonitor {
	return &AdaptiveMonitor{
		cfg:    cfg,
		stream: stream,
		alpha:  0.3,
	}
}

func (am *AdaptiveMonitor) Start(ctx context.Context) {
	ticker := time.NewTicker(am.cfg.Adaptive.MeasurementWindow)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			am.evaluate()
		}
	}
}

func (am *AdaptiveMonitor) evaluate() {
	status := am.stream.GetStatus()

	currentThroughput := float64(status.CurrentBitrate)

	if am.ewmaThroughput == 0 {
		am.ewmaThroughput = currentThroughput
	} else {
		am.ewmaThroughput = am.alpha*currentThroughput + (1-am.alpha)*am.ewmaThroughput
	}

	utilizationRatio := am.ewmaThroughput / float64(status.TargetBitrate)

	log.WithFields(log.Fields{
		"camera_id":         am.stream.cameraID,
		"current_bitrate":   status.CurrentBitrate,
		"target_bitrate":    status.TargetBitrate,
		"ewma_throughput":   am.ewmaThroughput,
		"utilization_ratio": utilizationRatio,
	}).Debug("Adaptive bitrate evaluation")

	if utilizationRatio < am.cfg.Adaptive.BitrateThreshold {
		am.downgradeQuality()
	} else if utilizationRatio > 0.95 {
		am.upgradeQuality()
	}
}

func (am *AdaptiveMonitor) downgradeQuality() {
	currentProfile := am.stream.bitrateProfile
	ladder := am.cfg.Adaptive.Bitrateladder

	currentIdx := -1
	for i, profile := range ladder {
		if profile.Name == currentProfile.Name {
			currentIdx = i
			break
		}
	}

	if currentIdx < len(ladder)-1 {
		newProfile := ladder[currentIdx+1]

		log.WithFields(log.Fields{
			"camera_id":   am.stream.cameraID,
			"old_profile": currentProfile.Name,
			"new_profile": newProfile.Name,
			"old_bitrate": currentProfile.Bitrate,
			"new_bitrate": newProfile.Bitrate,
		}).Info("Downgrading stream quality")

		am.applyProfile(newProfile)
	}
}

func (am *AdaptiveMonitor) upgradeQuality() {
	currentProfile := am.stream.bitrateProfile
	ladder := am.cfg.Adaptive.Bitrateladder

	currentIdx := -1
	for i, profile := range ladder {
		if profile.Name == currentProfile.Name {
			currentIdx = i
			break
		}
	}

	if currentIdx > 0 {
		newProfile := ladder[currentIdx-1]

		log.WithFields(log.Fields{
			"camera_id":   am.stream.cameraID,
			"old_profile": currentProfile.Name,
			"new_profile": newProfile.Name,
			"old_bitrate": currentProfile.Bitrate,
			"new_bitrate": newProfile.Bitrate,
		}).Info("Upgrading stream quality")

		am.applyProfile(newProfile)
	}
}

func (am *AdaptiveMonitor) applyProfile(profile config.BitrateProfile) {
	am.stream.mu.Lock()
	defer am.stream.mu.Unlock()

	am.stream.bitrateProfile = profile
	am.stream.targetBitrate = profile.Bitrate
	am.stream.currentFPS = profile.FPS
	am.stream.resolution = profile.Resolution
}