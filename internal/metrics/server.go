package metrics

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	log "github.com/sirupsen/logrus"
)

var (
	ActiveCameras = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "edge_agent_active_cameras",
		Help: "Number of active cameras",
	})

	ActiveStreams = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "edge_agent_active_streams",
		Help: "Number of active streams",
	})

	StreamBitrate = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "edge_agent_stream_bitrate_bps",
			Help: "Current stream bitrate in bits per second",
		},
		[]string{"camera_id", "camera_name"},
	)

	StreamFPS = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "edge_agent_stream_fps",
			Help: "Current stream frames per second",
		},
		[]string{"camera_id", "camera_name"},
	)

	StreamErrors = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "edge_agent_stream_errors_total",
			Help: "Total number of stream errors",
		},
		[]string{"camera_id", "camera_name", "error_type"},
	)

	BytesSent = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "edge_agent_bytes_sent_total",
			Help: "Total bytes sent",
		},
		[]string{"camera_id", "camera_name"},
	)

	PacketsLost = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "edge_agent_packets_lost_total",
			Help: "Total packets lost",
		},
		[]string{"camera_id", "camera_name"},
	)

	AgentUptime = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "edge_agent_uptime_seconds",
		Help: "Agent uptime in seconds",
	})

	ONVIFDiscoveries = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "edge_agent_onvif_discoveries_total",
		Help: "Total number of ONVIF discovery attempts",
	})

	ONVIFCamerasDiscovered = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "edge_agent_onvif_cameras_discovered",
		Help: "Number of cameras discovered via ONVIF",
	})
)

func init() {
	prometheus.MustRegister(ActiveCameras)
	prometheus.MustRegister(ActiveStreams)
	prometheus.MustRegister(StreamBitrate)
	prometheus.MustRegister(StreamFPS)
	prometheus.MustRegister(StreamErrors)
	prometheus.MustRegister(BytesSent)
	prometheus.MustRegister(PacketsLost)
	prometheus.MustRegister(AgentUptime)
	prometheus.MustRegister(ONVIFDiscoveries)
	prometheus.MustRegister(ONVIFCamerasDiscovered)
}

type Server struct {
	port      int
	server    *http.Server
	startTime time.Time
}

func NewServer(port int) *Server {
	return &Server{
		port:      port,
		startTime: time.Now(),
	}
}

func (s *Server) Start() error {
	router := mux.NewRouter()

	router.Handle("/metrics", promhttp.Handler())
	router.HandleFunc("/health", s.healthHandler).Methods("GET")
	router.HandleFunc("/ready", s.readinessHandler).Methods("GET")

	s.server = &http.Server{
		Addr:         fmt.Sprintf(":%d", s.port),
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Infof("Metrics server listening on port %d", s.port)

	go s.updateUptime()

	return s.server.ListenAndServe()
}

func (s *Server) Stop(ctx context.Context) error {
	log.Info("Stopping metrics server")

	if err := s.server.Shutdown(ctx); err != nil {
		return fmt.Errorf("failed to shutdown metrics server: %w", err)
	}

	log.Info("Metrics server stopped")
	return nil
}

func (s *Server) healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"healthy","uptime":"` + time.Since(s.startTime).String() + `"}`))
}

func (s *Server) readinessHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ready"}`))
}

func (s *Server) updateUptime() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		AgentUptime.Set(time.Since(s.startTime).Seconds())
	}
}