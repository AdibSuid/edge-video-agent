# discovery.py
from onvif import ONVIFCamera
from zeep.exceptions import Fault
import socket
import threading
import time

class ONVIFDiscovery:
    """ONVIF camera discovery and management"""
    
    def __init__(self):
        self.discovered_cameras = []
        self.discovery_lock = threading.Lock()

    def discover_cameras(self, timeout=5):
        """
        Discover ONVIF cameras on local network
        
        Args:
            timeout: Discovery timeout in seconds
            
        Returns:
            list: List of discovered camera dictionaries
        """
        self.discovered_cameras = []
        
        # WS-Discovery multicast
        discovery_thread = threading.Thread(
            target=self._ws_discovery,
            args=(timeout,),
            daemon=True
        )
        discovery_thread.start()
        discovery_thread.join(timeout + 1)
        
        return self.discovered_cameras

    def _ws_discovery(self, timeout):
        """Perform WS-Discovery on local network"""
        import xml.etree.ElementTree as ET
        
        # WS-Discovery probe message
        probe_msg = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
            '<s:Header>'
            '<a:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</a:Action>'
            '<a:MessageID>uuid:' + self._generate_uuid() + '</a:MessageID>'
            '<a:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</a:To>'
            '</s:Header>'
            '<s:Body>'
            '<Probe xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
            '<d:Types xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
            'xmlns:dp0="http://www.onvif.org/ver10/network/wsdl">dp0:NetworkVideoTransmitter</d:Types>'
            '</Probe>'
            '</s:Body>'
            '</s:Envelope>'
        ).encode('utf-8')
        
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        
        # Multicast address for WS-Discovery
        multicast_addr = ('239.255.255.250', 3702)
        
        try:
            # Send probe
            sock.sendto(probe_msg, multicast_addr)
            
            # Receive responses
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(65536)
                    self._parse_probe_match(data, addr[0])
                except socket.timeout:
                    break
                except Exception as e:
                    print(f"Discovery error: {e}")
                    
        finally:
            sock.close()

    def _parse_probe_match(self, data, ip):
        """Parse WS-Discovery probe match response"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(data.decode('utf-8'))
            
            # Extract XAddrs (camera URLs)
            namespaces = {
                'soap': 'http://www.w3.org/2003/05/soap-envelope',
                'd': 'http://schemas.xmlsoap.org/ws/2005/04/discovery'
            }
            
            xaddrs = root.find('.//d:XAddrs', namespaces)
            if xaddrs is not None and xaddrs.text:
                urls = xaddrs.text.split()
                
                with self.discovery_lock:
                    # Check if already discovered
                    if not any(cam['ip'] == ip for cam in self.discovered_cameras):
                        self.discovered_cameras.append({
                            'ip': ip,
                            'urls': urls,
                            'name': f"Camera {ip}",
                            'manufacturer': 'Unknown',
                            'model': 'Unknown'
                        })
                        
        except Exception as e:
            print(f"Parse error: {e}")

    def _generate_uuid(self):
        """Generate simple UUID for WS-Discovery"""
        import uuid
        return str(uuid.uuid4())

    def get_camera_info(self, ip, port=80, user='admin', password='admin'):
        """
        Get detailed camera information via ONVIF
        
        Args:
            ip: Camera IP address
            port: ONVIF port
            user: Username
            password: Password
            
        Returns:
            dict: Camera information or None on failure
        """
        try:
            camera = ONVIFCamera(ip, port, user, password)
            
            # Get device information
            device_service = camera.devicemgmt.create_devicemgmt_service()
            device_info = device_service.GetDeviceInformation()
            
            # Get media profiles
            media_service = camera.media.create_media_service()
            profiles = media_service.GetProfiles()
            
            # Get stream URIs
            stream_uris = []
            for profile in profiles:
                try:
                    stream_setup = {
                        'Stream': 'RTP-Unicast',
                        'Transport': {'Protocol': 'RTSP'}
                    }
                    uri = media_service.GetStreamUri({
                        'StreamSetup': stream_setup,
                        'ProfileToken': profile.token
                    })
                    stream_uris.append(str(uri.Uri))
                except:
                    pass
            
            return {
                'ip': ip,
                'port': port,
                'manufacturer': str(device_info.Manufacturer),
                'model': str(device_info.Model),
                'firmware': str(device_info.FirmwareVersion),
                'serial': str(device_info.SerialNumber),
                'stream_uris': stream_uris,
                'profiles': [p.Name for p in profiles]
            }
            
        except Exception as e:
            print(f"Failed to get camera info for {ip}: {e}")
            return None

    def test_rtsp_url(self, rtsp_url, timeout=5):
        """
        Test if RTSP URL is accessible
        
        Args:
            rtsp_url: RTSP URL to test
            timeout: Timeout in seconds
            
        Returns:
            bool: True if accessible
        """
        import cv2
        
        try:
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
            
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                return ret and frame is not None
            
            return False
            
        except Exception as e:
            print(f"RTSP test failed: {e}")
            return False

# Simple network scanner fallback
def scan_network_ports(port=80, subnet='192.168.1', timeout=1):
    """
    Simple port scanner for finding cameras
    
    Args:
        port: Port to scan
        subnet: Subnet to scan (e.g., '192.168.1')
        timeout: Socket timeout
        
    Returns:
        list: List of responsive IP addresses
    """
    responsive_ips = []
    
    def check_port(ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                responsive_ips.append(ip)
        except:
            pass
    
    threads = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        thread = threading.Thread(target=check_port, args=(ip,), daemon=True)
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    return responsive_ips