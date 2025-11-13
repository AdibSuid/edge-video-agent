package camera

import (
	"fmt"
	"sync"
	"time"
)

type Camera struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	RTSPURL     string            `json:"rtsp_url"`
	Username    string            `json:"username,omitempty"`
	Password    string            `json:"password,omitempty"`
	Type        string            `json:"type"`
	Status      string            `json:"status"`
	AddedAt     time.Time         `json:"added_at"`
	LastSeen    time.Time         `json:"last_seen"`
	Metadata    map[string]string `json:"metadata,omitempty"`
	StreamID    string            `json:"stream_id,omitempty"`
	Enabled     bool              `json:"enabled"`
}

type Registry struct {
	mu      sync.RWMutex
	cameras map[string]Camera
}

func NewRegistry() (*Registry, error) {
	return &Registry{
		cameras: make(map[string]Camera),
	}, nil
}

func (r *Registry) Add(cam Camera) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if cam.ID == "" {
		return fmt.Errorf("camera ID is required")
	}
	if cam.RTSPURL == "" {
		return fmt.Errorf("camera RTSP URL is required")
	}
	if _, exists := r.cameras[cam.ID]; exists {
		return fmt.Errorf("camera with ID %s already exists", cam.ID)
	}

	if cam.Status == "" {
		cam.Status = "registered"
	}
	if cam.AddedAt.IsZero() {
		cam.AddedAt = time.Now()
	}
	cam.LastSeen = time.Now()
	cam.Enabled = true

	r.cameras[cam.ID] = cam
	return nil
}

func (r *Registry) Remove(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.cameras[id]; !exists {
		return fmt.Errorf("camera not found: %s", id)
	}
	delete(r.cameras, id)
	return nil
}

func (r *Registry) Get(id string) (Camera, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	cam, exists := r.cameras[id]
	return cam, exists
}

func (r *Registry) Update(id string, updateFunc func(*Camera) error) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	cam, exists := r.cameras[id]
	if !exists {
		return fmt.Errorf("camera not found: %s", id)
	}

	if err := updateFunc(&cam); err != nil {
		return err
	}

	r.cameras[id] = cam
	return nil
}

func (r *Registry) List() []Camera {
	r.mu.RLock()
	defer r.mu.RUnlock()

	cameras := make([]Camera, 0, len(r.cameras))
	for _, cam := range r.cameras {
		cameras = append(cameras, cam)
	}
	return cameras
}