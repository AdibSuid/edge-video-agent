package onvif

import (
	"context"
	"encoding/xml"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/yourorg/edge-video-agent/internal/config"

	log "github.com/sirupsen/logrus"
)

type Camera struct {
	UUID            string
	Name            string
	Manufacturer    string
	Model           string
	FirmwareVersion string
	XAddr           string
	StreamURIs      []string
	Username        string
	Password        string
}

type Discovery struct {
	cfg       config.ONVIFConfig
	mu        sync.RWMutex
	cameras   map[string]Camera
	callbacks []func([]Camera)
}

func NewDiscovery(cfg config.ONVIFConfig) (*Discovery, error) {
	return &Discovery{
		cfg:     cfg,
		cameras: make(map[string]Camera),
	}, nil
}

func (d *Discovery) Start(ctx context.Context, callback func([]Camera)) error {
	d.mu.Lock()
	d.callbacks = append(d.callbacks, callback)
	d.mu.Unlock()

	if err := d.Discover(); err != nil {
		log.Warnf("Initial ONVIF discovery failed: %v", err)
	}

	ticker := time.NewTicker(d.cfg.DiscoveryInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			if err := d.Discover(); err != nil {
				log.Warnf("ONVIF discovery failed: %v", err)
			}
		}
	}
}

func (d *Discovery) Discover() error {
	log.Info("Starting ONVIF discovery")

	interfaces, err := d.getInterfaces()
	if err != nil {
		return fmt.Errorf("failed to get network interfaces: %w", err)
	}

	var wg sync.WaitGroup
	discoveredCameras := make(map[string]Camera)
	var mu sync.Mutex

	for _, iface := range interfaces {
		wg.Add(1)
		go func(iface net.Interface) {
			defer wg.Done()

			cameras, err := d.discoverOnInterface(iface)
			if err != nil {
				log.Warnf("Discovery failed on interface %s: %v", iface.Name, err)
				return
			}

			mu.Lock()
			for uuid, cam := range cameras {
				discoveredCameras[uuid] = cam
			}
			mu.Unlock()
		}(iface)
	}

	wg.Wait()

	d.mu.Lock()
	d.cameras = discoveredCameras
	cameras := make([]Camera, 0, len(discoveredCameras))
	for _, cam := range discoveredCameras {
		cameras = append(cameras, cam)
	}
	d.mu.Unlock()

	log.Infof("ONVIF discovery completed: found %d cameras", len(cameras))

	d.mu.RLock()
	callbacks := d.callbacks
	d.mu.RUnlock()

	for _, callback := range callbacks {
		go callback(cameras)
	}

	return nil
}

func (d *Discovery) getInterfaces() ([]net.Interface, error) {
	allInterfaces, err := net.Interfaces()
	if err != nil {
		return nil, err
	}

	if len(d.cfg.Interfaces) > 0 {
		var interfaces []net.Interface
		for _, iface := range allInterfaces {
			for _, name := range d.cfg.Interfaces {
				if iface.Name == name {
					interfaces = append(interfaces, iface)
					break
				}
			}
		}
		return interfaces, nil
	}

	var interfaces []net.Interface
	for _, iface := range allInterfaces {
		if iface.Flags&net.FlagUp != 0 && iface.Flags&net.FlagMulticast != 0 {
			interfaces = append(interfaces, iface)
		}
	}

	return interfaces, nil
}

func (d *Discovery) discoverOnInterface(iface net.Interface) (map[string]Camera, error) {
	addr, err := net.ResolveUDPAddr("udp4", "239.255.255.250:3702")
	if err != nil {
		return nil, err
	}

	conn, err := net.ListenMulticastUDP("udp4", &iface, addr)
	if err != nil {
		return nil, err
	}
	defer conn.Close()

	conn.SetReadDeadline(time.Now().Add(d.cfg.Timeout))

	probeMsg := buildProbeMessage()
	if _, err := conn.WriteToUDP([]byte(probeMsg), addr); err != nil {
		return nil, err
	}

	cameras := make(map[string]Camera)
	buf := make([]byte, 8192)

	for {
		n, _, err := conn.ReadFromUDP(buf)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				break
			}
			return nil, err
		}

		cam, err := d.parseProbeMatch(buf[:n])
		if err != nil {
			log.Debugf("Failed to parse probe match: %v", err)
			continue
		}

		if cam != nil {
			cameras[cam.UUID] = *cam
		}
	}

	return cameras, nil
}

func (d *Discovery) parseProbeMatch(data []byte) (*Camera, error) {
	var envelope struct {
		Body struct {
			ProbeMatches struct {
				ProbeMatch []struct {
					EndpointReference struct {
						Address string `xml:"Address"`
					} `xml:"EndpointReference"`
					Scopes string `xml:"Scopes"`
					XAddrs string `xml:"XAddrs"`
				} `xml:"ProbeMatch"`
			} `xml:"ProbeMatches"`
		} `xml:"Body"`
	}

	if err := xml.Unmarshal(data, &envelope); err != nil {
		return nil, err
	}

	if len(envelope.Body.ProbeMatches.ProbeMatch) == 0 {
		return nil, nil
	}

	match := envelope.Body.ProbeMatches.ProbeMatch[0]

	uuid := strings.TrimPrefix(match.EndpointReference.Address, "urn:uuid:")

	scopes := parseScopes(match.Scopes)

	xaddrs := strings.Fields(match.XAddrs)
	if len(xaddrs) == 0 {
		return nil, fmt.Errorf("no XAddrs found")
	}

	cam := &Camera{
		UUID:         uuid,
		Name:         scopes["name"],
		Manufacturer: scopes["manufacturer"],
		Model:        scopes["hardware"],
		XAddr:        xaddrs[0],
	}

	cam.StreamURIs = []string{
		fmt.Sprintf("rtsp://%s/stream1", extractHost(cam.XAddr)),
	}

	return cam, nil
}

func buildProbeMessage() string {
	return `<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" 
            xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <s:Header>
    <a:Action s:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>
    <a:MessageID>uuid:` + generateUUID() + `</a:MessageID>
    <a:ReplyTo>
      <a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address>
    </a:ReplyTo>
    <a:To s:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>
  </s:Header>
  <s:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </s:Body>
</s:Envelope>`
}

func parseScopes(scopesStr string) map[string]string {
	scopes := make(map[string]string)
	parts := strings.Fields(scopesStr)

	for _, part := range parts {
		if strings.Contains(part, "onvif://www.onvif.org/") {
			keyval := strings.TrimPrefix(part, "onvif://www.onvif.org/")
			kvparts := strings.SplitN(keyval, "/", 2)
			if len(kvparts) == 2 {
				scopes[kvparts[0]] = kvparts[1]
			}
		}
	}

	return scopes
}

func extractHost(urlStr string) string {
	parts := strings.Split(strings.TrimPrefix(urlStr, "http://"), "/")
	if len(parts) > 0 {
		return parts[0]
	}
	return urlStr
}

func generateUUID() string {
	return fmt.Sprintf("%d-%d", time.Now().UnixNano(), time.Now().Unix())
}

func (d *Discovery) GetCameras() []Camera {
	d.mu.RLock()
	defer d.mu.RUnlock()

	cameras := make([]Camera, 0, len(d.cameras))
	for _, cam := range d.cameras {
		cameras = append(cameras, cam)
	}

	return cameras
}