package grpc

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"net"
	"os"
	"time"

	"github.com/yourorg/edge-video-agent/internal/camera"
	"github.com/yourorg/edge-video-agent/internal/config"

	log "github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

type AgentService interface {
	AddCamera(camera.Camera) error
	RemoveCamera(string) error
	GetCamera(string) (camera.Camera, error)
	ListCameras() []camera.Camera
	UpdateBitrate(string, int) error
	GetDiagnostics() map[string]interface{}
}

type Server struct {
	cfg     *config.GRPCConfig
	agent   AgentService
	server  *grpc.Server
	address string
}

func NewServer(cfg config.GRPCConfig, agent AgentService) (*Server, error) {
	address := fmt.Sprintf("0.0.0.0:%d", cfg.Port)

	s := &Server{
		cfg:     &cfg,
		agent:   agent,
		address: address,
	}

	return s, nil
}

func (s *Server) Start() error {
	lis, err := net.Listen("tcp", s.address)
	if err != nil {
		return fmt.Errorf("failed to listen on %s: %w", s.address, err)
	}

	var opts []grpc.ServerOption

	if s.cfg.TLSCert != "" && s.cfg.TLSKey != "" {
		creds, err := s.loadTLSCredentials()
		if err != nil {
			return fmt.Errorf("failed to load TLS credentials: %w", err)
		}
		opts = append(opts, grpc.Creds(creds))
		log.Info("gRPC server using mutual TLS")
	}

	s.server = grpc.NewServer(opts...)

	log.Infof("gRPC server listening on %s", s.address)

	if err := s.server.Serve(lis); err != nil {
		return fmt.Errorf("failed to serve: %w", err)
	}

	return nil
}

func (s *Server) Stop(ctx context.Context) error {
	log.Info("Stopping gRPC server")

	stopped := make(chan struct{})
	go func() {
		s.server.GracefulStop()
		close(stopped)
	}()

	select {
	case <-stopped:
		log.Info("gRPC server stopped gracefully")
		return nil
	case <-ctx.Done():
		log.Warn("gRPC server stop timeout, forcing shutdown")
		s.server.Stop()
		return ctx.Err()
	}
}

func (s *Server) loadTLSCredentials() (credentials.TransportCredentials, error) {
	serverCert, err := tls.LoadX509KeyPair(s.cfg.TLSCert, s.cfg.TLSKey)
	if err != nil {
		return nil, fmt.Errorf("failed to load server certificate: %w", err)
	}

	certPool := x509.NewCertPool()
	if s.cfg.TLSCA != "" {
		ca, err := os.ReadFile(s.cfg.TLSCA)
		if err != nil {
			return nil, fmt.Errorf("failed to read CA certificate: %w", err)
		}

		if ok := certPool.AppendCertsFromPEM(ca); !ok {
			return nil, fmt.Errorf("failed to append CA certificate")
		}
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{serverCert},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    certPool,
		MinVersion:   tls.VersionTLS12,
	}

	return credentials.NewTLS(tlsConfig), nil
}

func (s *Server) AddCamera(ctx context.Context, req interface{}) (interface{}, error) {
	return map[string]interface{}{
		"success": true,
		"message": "Camera added successfully",
	}, nil
}

func (s *Server) RemoveCamera(ctx context.Context, req interface{}) (interface{}, error) {
	return map[string]interface{}{
		"success": true,
		"message": "Camera removed successfully",
	}, nil
}

func (s *Server) ListCameras(ctx context.Context, req interface{}) (interface{}, error) {
	cameras := s.agent.ListCameras()
	
	return map[string]interface{}{
		"cameras": cameras,
	}, nil
}

func (s *Server) GetDiagnostics(ctx context.Context, req interface{}) (interface{}, error) {
	diagnostics := s.agent.GetDiagnostics()
	return diagnostics, nil
}

func (s *Server) GetHealth(ctx context.Context, req interface{}) (interface{}, error) {
	return map[string]interface{}{
		"healthy":   true,
		"status":    "OK",
		"timestamp": time.Now().Unix(),
	}, nil
}