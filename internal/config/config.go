package config

import (
	"fmt"
	"os"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	Agent    AgentConfig    `mapstructure:"agent"`
	Cloud    CloudConfig    `mapstructure:"cloud"`
	ONVIF    ONVIFConfig    `mapstructure:"onvif"`
	Encoding EncodingConfig `mapstructure:"encoding"`
	Adaptive AdaptiveConfig `mapstructure:"adaptive"`
	Cameras  []CameraConfig `mapstructure:"cameras"`
	Telegram TelegramConfig `mapstructure:"telegram"`
	GRPC     GRPCConfig     `mapstructure:"grpc"`
	Metrics  MetricsConfig  `mapstructure:"metrics"`
	Logging  LoggingConfig  `mapstructure:"logging"`
	Storage  StorageConfig  `mapstructure:"storage"`
}

type CameraConfig struct {
	ID       string            `mapstructure:"id"`
	Name     string            `mapstructure:"name"`
	RTSPURL  string            `mapstructure:"rtsp_url"`
	Username string            `mapstructure:"username"`
	Password string            `mapstructure:"password"`
	Type     string            `mapstructure:"type"`
	Metadata map[string]string `mapstructure:"metadata"`
	Enabled  bool              `mapstructure:"enabled"`
}

type AgentConfig struct {
	ID   string `mapstructure:"id"`
	Name string `mapstructure:"name"`
}

type CloudConfig struct {
	SRTEndpoint   string `mapstructure:"srt_endpoint"`
	SRTPassphrase string `mapstructure:"srt_passphrase"`
	SRTLatency    int    `mapstructure:"srt_latency"`
	GRPCEndpoint  string `mapstructure:"grpc_endpoint"`
	TLSCert       string `mapstructure:"tls_cert"`
	TLSKey        string `mapstructure:"tls_key"`
	TLSCA         string `mapstructure:"tls_ca"`
}

type ONVIFConfig struct {
	Enabled           bool          `mapstructure:"enabled"`
	DiscoveryInterval time.Duration `mapstructure:"discovery_interval"`
	Timeout           time.Duration `mapstructure:"timeout"`
	Interfaces        []string      `mapstructure:"interfaces"`
}

type EncodingConfig struct {
	Preset            string `mapstructure:"preset"`
	Tune              string `mapstructure:"tune"`
	DefaultBitrate    int    `mapstructure:"default_bitrate"`
	DefaultFPS        int    `mapstructure:"default_fps"`
	DefaultResolution string `mapstructure:"default_resolution"`
	GOPSize           int    `mapstructure:"gop_size"`
	MaxRate           int    `mapstructure:"max_rate"`
	BufSize           int    `mapstructure:"buf_size"`
}

type AdaptiveConfig struct {
	Enabled           bool                `mapstructure:"enabled"`
	MeasurementWindow time.Duration       `mapstructure:"measurement_window"`
	BitrateThreshold  float64             `mapstructure:"bitrate_threshold"`
	Bitrateladder     []BitrateProfile    `mapstructure:"bitrate_ladder"`
}

type BitrateProfile struct {
	Name       string `mapstructure:"name"`
	Bitrate    int    `mapstructure:"bitrate"`
	FPS        int    `mapstructure:"fps"`
	Resolution string `mapstructure:"resolution"`
}

type TelegramConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	BotToken string `mapstructure:"bot_token"`
	ChatID   int64  `mapstructure:"chat_id"`
}

type GRPCConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Port    int    `mapstructure:"port"`
	TLSCert string `mapstructure:"tls_cert"`
	TLSKey  string `mapstructure:"tls_key"`
	TLSCA   string `mapstructure:"tls_ca"`
}

type MetricsConfig struct {
	Enabled bool `mapstructure:"enabled"`
	Port    int  `mapstructure:"port"`
}

type LoggingConfig struct {
	Level  string `mapstructure:"level"`
	Format string `mapstructure:"format"`
	Output string `mapstructure:"output"`
}

type StorageConfig struct {
	BufferPath     string        `mapstructure:"buffer_path"`
	BufferSize     int64         `mapstructure:"buffer_size"`
	BufferDuration time.Duration `mapstructure:"buffer_duration"`
}

func Load(path string) (*Config, error) {
	v := viper.New()
	setDefaults(v)
	v.SetConfigFile(path)
	v.SetConfigType("yaml")
	v.AutomaticEnv()
	v.SetEnvPrefix("EDGE_AGENT")

	if err := v.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			return nil, fmt.Errorf("config file not found: %s", path)
		}
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	if err := validate(&cfg); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &cfg, nil
}

func setDefaults(v *viper.Viper) {
	v.SetDefault("agent.id", getHostname())
	v.SetDefault("agent.name", "Edge Agent")
	v.SetDefault("cloud.srt_latency", 1000)
	v.SetDefault("onvif.enabled", true)
	v.SetDefault("onvif.discovery_interval", "300s")
	v.SetDefault("onvif.timeout", "10s")
	v.SetDefault("encoding.preset", "superfast")
	v.SetDefault("encoding.tune", "zerolatency")
	v.SetDefault("encoding.default_bitrate", 2000000)
	v.SetDefault("encoding.default_fps", 15)
	v.SetDefault("encoding.default_resolution", "1280x720")
	v.SetDefault("encoding.gop_size", 30)
	v.SetDefault("adaptive.enabled", true)
	v.SetDefault("adaptive.measurement_window", "30s")
	v.SetDefault("adaptive.bitrate_threshold", 0.8)
	v.SetDefault("telegram.enabled", false)
	v.SetDefault("grpc.enabled", true)
	v.SetDefault("grpc.port", 50051)
	v.SetDefault("metrics.enabled", true)
	v.SetDefault("metrics.port", 8080)
	v.SetDefault("logging.level", "info")
	v.SetDefault("logging.format", "json")
	v.SetDefault("logging.output", "stdout")
	v.SetDefault("storage.buffer_path", "/var/lib/edge-agent/buffer")
	v.SetDefault("storage.buffer_size", 1073741824)
	v.SetDefault("storage.buffer_duration", "60s")
}

func validate(cfg *Config) error {
	if cfg.Agent.ID == "" {
		return fmt.Errorf("agent.id is required")
	}
	if cfg.Cloud.SRTEndpoint == "" {
		return fmt.Errorf("cloud.srt_endpoint is required")
	}
	if cfg.Cloud.SRTPassphrase == "" {
		return fmt.Errorf("cloud.srt_passphrase is required")
	}
	if cfg.Telegram.Enabled {
		if cfg.Telegram.BotToken == "" {
			return fmt.Errorf("telegram.bot_token is required when telegram is enabled")
		}
		if cfg.Telegram.ChatID == 0 {
			return fmt.Errorf("telegram.chat_id is required when telegram is enabled")
		}
	}
	return nil
}

func getHostname() string {
	hostname, err := os.Hostname()
	if err != nil {
		return "edge-agent"
	}
	return hostname
}