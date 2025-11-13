package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/yourorg/edge-video-agent/internal/agent"
	"github.com/yourorg/edge-video-agent/internal/alert"
	"github.com/yourorg/edge-video-agent/internal/config"
	"github.com/yourorg/edge-video-agent/internal/grpc"
	"github.com/yourorg/edge-video-agent/internal/metrics"
	"github.com/yourorg/edge-video-agent/internal/onvif"

	log "github.com/sirupsen/logrus"
)

var (
	version   = "dev"
	buildTime = "unknown"
	gitCommit = "unknown"
)

func main() {
	configPath := flag.String("config", "configs/config.yaml", "Path to configuration file")
	showVersion := flag.Bool("version", false, "Show version information")
	flag.Parse()

	if *showVersion {
		fmt.Printf("Edge Video Agent\nVersion: %s\nBuild Time: %s\nGit Commit: %s\n", version, buildTime, gitCommit)
		os.Exit(0)
	}

	cfg, err := config.Load(*configPath)
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	setupLogging(cfg)

	log.WithFields(log.Fields{
		"version":    version,
		"build_time": buildTime,
		"git_commit": gitCommit,
		"agent_id":   cfg.Agent.ID,
	}).Info("Starting Edge Video Agent")

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var alerter *alert.TelegramAlerter
	if cfg.Telegram.Enabled {
		alerter, err = alert.NewTelegramAlerter(cfg.Telegram)
		if err != nil {
			log.Warnf("Failed to initialize Telegram alerter: %v", err)
		} else {
			log.Info("Telegram alerter initialized")
			alerter.SendAlert(alert.AlertInfo, "Edge Agent Started",
				fmt.Sprintf("Agent %s (%s) has started successfully", cfg.Agent.ID, cfg.Agent.Name))
		}
	}

	var onvifDiscovery *onvif.Discovery
	if cfg.ONVIF.Enabled {
		onvifDiscovery, err = onvif.NewDiscovery(cfg.ONVIF)
		if err != nil {
			log.Fatalf("Failed to initialize ONVIF discovery: %v", err)
		}
		log.Info("ONVIF discovery initialized")
	}

	edgeAgent, err := agent.NewAgent(cfg, alerter, onvifDiscovery)
	if err != nil {
		log.Fatalf("Failed to initialize agent: %v", err)
	}

	metricsServer := metrics.NewServer(cfg.Metrics.Port)
	go func() {
		if err := metricsServer.Start(); err != nil {
			log.Errorf("Metrics server error: %v", err)
		}
	}()
	log.Infof("Metrics server started on port %d", cfg.Metrics.Port)

	grpcServer, err := grpc.NewServer(cfg.GRPC, edgeAgent)
	if err != nil {
		log.Fatalf("Failed to initialize gRPC server: %v", err)
	}
	go func() {
		if err := grpcServer.Start(); err != nil {
			log.Errorf("gRPC server error: %v", err)
		}
	}()
	log.Infof("gRPC control plane started on port %d", cfg.GRPC.Port)

	if err := edgeAgent.Start(ctx); err != nil {
		log.Fatalf("Failed to start agent: %v", err)
	}

	if onvifDiscovery != nil {
		go func() {
			if err := onvifDiscovery.Start(ctx, func(cameras []onvif.Camera) {
				log.Infof("Discovered %d cameras via ONVIF", len(cameras))
				for _, cam := range cameras {
					if err := edgeAgent.AddDiscoveredCamera(cam); err != nil {
						log.Warnf("Failed to add discovered camera %s: %v", cam.Name, err)
					}
				}
			}); err != nil {
				log.Errorf("ONVIF discovery error: %v", err)
			}
		}()
		log.Info("ONVIF discovery started")
	}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	<-sigChan
	log.Info("Shutdown signal received, gracefully stopping...")

	if alerter != nil {
		alerter.SendAlert(alert.AlertWarning, "Edge Agent Stopping",
			fmt.Sprintf("Agent %s (%s) is shutting down", cfg.Agent.ID, cfg.Agent.Name))
	}

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := edgeAgent.Stop(shutdownCtx); err != nil {
		log.Errorf("Error stopping agent: %v", err)
	}

	if err := grpcServer.Stop(shutdownCtx); err != nil {
		log.Errorf("Error stopping gRPC server: %v", err)
	}

	if err := metricsServer.Stop(shutdownCtx); err != nil {
		log.Errorf("Error stopping metrics server: %v", err)
	}

	log.Info("Edge Video Agent stopped")
}

func setupLogging(cfg *config.Config) {
	level, err := log.ParseLevel(cfg.Logging.Level)
	if err != nil {
		log.Warnf("Invalid log level %s, using info", cfg.Logging.Level)
		level = log.InfoLevel
	}
	log.SetLevel(level)

	if cfg.Logging.Format == "json" {
		log.SetFormatter(&log.JSONFormatter{
			TimestampFormat: time.RFC3339Nano,
			FieldMap: log.FieldMap{
				log.FieldKeyTime:  "timestamp",
				log.FieldKeyLevel: "level",
				log.FieldKeyMsg:   "message",
			},
		})
	} else {
		log.SetFormatter(&log.TextFormatter{
			FullTimestamp:   true,
			TimestampFormat: time.RFC3339,
		})
	}

	if cfg.Logging.Output != "" && cfg.Logging.Output != "stdout" {
		file, err := os.OpenFile(cfg.Logging.Output, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
		if err != nil {
			log.Warnf("Failed to open log file %s: %v", cfg.Logging.Output, err)
		} else {
			log.SetOutput(file)
		}
	}
}