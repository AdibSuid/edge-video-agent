# discovery.py
from onvif import ONVIFCamera
from zeep.exceptions import Fault
import socket
import threading
import time
import uuid
import re
import concurrent.futures
from typing import List, Dict, Optional

class ONVIFDiscovery:
    """ONVIF camera discovery and management"""
    
    COMMON_ONVIF_PORTS = [2020, 80, 8080, 8000, 8899, 10080]
    
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
        print(f"[*] Starting ONVIF camera discovery (timeout: {timeout}s)...")
        
        self.discovered_cameras = []
        
        # Try WS-Discovery first
        discovery_thread = threading.Thread(
            target=self._ws_discovery,
            args=(timeout,),
            daemon=True
        )
        discovery_thread.start()
        discovery_thread.join(timeout + 1)
        
        # If WS-Discovery failed, use network scan
        if len(self.discovered_cameras) == 0:
            print("[*] WS-Discovery failed, attempting network scan...")
            scanned_cameras = self._scan_local_network()
            with self.discovery_lock:
                self.discovered_cameras.extend(scanned_cameras)
        
        print(f"[+] Found {len(self.discovered_cameras)} camera(s)")
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
            '<a:MessageID>uuid:' + str(uuid.uuid4()) + '</a:MessageID>'
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
            
            # Also try broadcast
            try:
                sock.sendto(probe_msg, ('255.255.255.255', 3702))
            except:
                pass
            
            # Receive responses
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(65536)
                    self._parse_probe_match(data, addr[0])
                except socket.timeout:
                    break
                except Exception as e:
                    pass
                    
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
                url = urls[0] if urls else None
                
                # Extract port from URL
                port = 80
                if url:
                    port_match = re.search(r':(\d+)/', url)
                    if port_match:
                        port = int(port_match.group(1))
                
                with self.discovery_lock:
                    # Check if already discovered
                    if not any(cam['ip'] == ip for cam in self.discovered_cameras):
                        self.discovered_cameras.append({
                            'ip': ip,
                            'port': port,
                            'url': url or f'http://{ip}:{port}/onvif/device_service',
                            'name': f"Camera {ip}",
                            'manufacturer': 'Unknown',
                            'model': 'Unknown'
                        })
                        
        except Exception as e:
            pass
    
    def _scan_local_network(self) -> List[Dict]:
        """Scan local network for ONVIF devices on common ports"""
        cameras = []
        
        try:
            # Get local IP and subnet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Calculate network range (assuming /24)
            ip_parts = local_ip.split('.')
            network_prefix = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"
            
            # Specific camera IPs to check first
            camera_ips = [
                ('192.168.1.102', 2020),
                ('192.168.1.103', 2020),
                ('192.168.1.113', 8080),
                ('192.168.1.133', 2020)
            ]
            
            print(f"[*] Checking known camera addresses...")
            for ip, port in camera_ips:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        cameras.append({
                            'ip': ip,
                            'port': port,
                            'url': f'http://{ip}:{port}/onvif/device_service',
                            'name': f'Camera {ip}',
                            'manufacturer': 'Unknown',
                            'model': 'Unknown'
                        })
                        print(f"[+] Found camera at {ip}:{port}")
                except:
                    pass
            
            # If fewer than 4 cameras found, do a full network scan
            if len(cameras) < 4:
                print(f"[*] Scanning {network_prefix}.1-254 on common ports...")
                
                def check_onvif(ip, port):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.5)
                        result = sock.connect_ex((ip, port))
                        sock.close()
                        if result == 0:
                            return (ip, port)
                    except:
                        pass
                    return None
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                    futures = []
                    for i in range(1, 255):
                        ip = f"{network_prefix}.{i}"
                        # Skip already found IPs
                        if any(c['ip'] == ip for c in cameras):
                            continue
                        for port in self.COMMON_ONVIF_PORTS:
                            futures.append(executor.submit(check_onvif, ip, port))
                    
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result:
                            ip, port = result
                            if (ip, port) not in [(c['ip'], c['port']) for c in cameras]:
                                # Only add if port is 2020, 8080, or 8000 (common camera ports)
                                if port in [2020, 8080, 8000]:
                                    cameras.append({
                                        'ip': ip,
                                        'port': port,
                                        'url': f'http://{ip}:{port}/onvif/device_service',
                                        'name': f'Camera {ip}',
                                        'manufacturer': 'Unknown',
                                        'model': 'Unknown'
                                    })
                                    print(f"[+] Found camera at {ip}:{port}")
        
        except Exception as e:
            print(f"[!] Network scan error: {e}")
        
        return cameras

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
            # Try to find WSDL files
            wsdl_dir = self._get_wsdl_dir()
            
            if wsdl_dir:
                camera = ONVIFCamera(ip, port, user, password, wsdl_dir=wsdl_dir)
            else:
                camera = ONVIFCamera(ip, port, user, password)
            
            # Get device information
            device_service = camera.create_devicemgmt_service()
            device_info = device_service.GetDeviceInformation()
            
            # Get media profiles
            media_service = camera.create_media_service()
            profiles = media_service.GetProfiles()
            
            # Get stream URIs with credentials embedded
            stream_uris = []
            profile_details = []
            
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
                    
                    rtsp_url = str(uri.Uri)
                    
                    # Extract suffix and build complete URL with credentials
                    suffix = self._extract_rtsp_suffix(rtsp_url)
                    complete_url = self._build_rtsp_url(ip, user, password, suffix)
                    
                    stream_uris.append(complete_url)
                    
                    profile_info = {
                        'name': str(profile.Name),
                        'token': str(profile.token),
                        'rtsp_url': rtsp_url,
                        'rtsp_suffix': suffix,
                        'complete_url': complete_url
                    }
                    
                    # Try to get resolution
                    try:
                        if hasattr(profile, 'VideoEncoderConfiguration'):
                            video_config = profile.VideoEncoderConfiguration
                            if hasattr(video_config, 'Resolution'):
                                profile_info['resolution'] = {
                                    'width': video_config.Resolution.Width,
                                    'height': video_config.Resolution.Height
                                }
                    except:
                        pass
                    
                    profile_details.append(profile_info)
                except Exception as e:
                    print(f"Failed to get stream URI for profile {profile.token}: {e}")
                    pass
            
            return {
                'ip': ip,
                'port': port,
                'manufacturer': str(device_info.Manufacturer),
                'model': str(device_info.Model),
                'firmware': str(device_info.FirmwareVersion),
                'serial': str(device_info.SerialNumber),
                'stream_uris': stream_uris,
                'profiles': profile_details
            }
            
        except Exception as e:
            print(f"Failed to get camera info for {ip}: {e}")
            return None
    
    def _get_wsdl_dir(self):
        """Get the correct WSDL directory path for onvif-zeep"""
        import os
        
        # Try to find WSDL files in common locations
        possible_paths = [
            '/home/raspberry/Documents/edge-video-agent/venv/lib/python3.4/site-packages/wsdl',
            '/home/raspberry/Documents/edge-video-agent/venv/lib/python3.11/site-packages/wsdl',
            '/usr/local/lib/python3.11/site-packages/wsdl',
            '/usr/lib/python3/dist-packages/wsdl',
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, 'devicemgmt.wsdl')):
                return path
        
        # If not found, return None to use default
        return None
    
    def _extract_rtsp_suffix(self, rtsp_url):
        """Extract the suffix/path from full RTSP URL"""
        import re
        
        # Remove credentials if present
        url = re.sub(r'rtsp://[^@]+@', 'rtsp://', rtsp_url)
        
        # Extract path after IP:PORT
        match = re.search(r'rtsp://[^/]+/(.+)', url)
        if match:
            return match.group(1)
        
        # Return original URL if pattern not matched
        return rtsp_url
    
    def _build_rtsp_url(self, ip, username, password, suffix, port=554):
        """Build complete RTSP URL with credentials"""
        import re
        
        # Handle suffix that might already contain port
        if suffix.startswith('rtsp://'):
            # Extract port if present in suffix
            port_match = re.search(r':(\d+)/', suffix)
            if port_match:
                port = int(port_match.group(1))
            # Extract just the path
            suffix = self._extract_rtsp_suffix(suffix)
        
        # Ensure suffix starts with /
        if not suffix.startswith('/'):
            suffix = '/' + suffix
        
        # Build URL with credentials
        return f"rtsp://{username}:{password}@{ip}:{port}{suffix}"

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