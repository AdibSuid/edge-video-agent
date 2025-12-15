# API to get RTSP URI from ONVIF
# ...existing code...

# Place this route after app = Flask(__name__)


# app.py
from flask import Flask, render_template, request, jsonify
import yaml
import json
from pathlib import Path
from datetime import datetime
import threading
import time

from streamer import Streamer
from discovery import ONVIFDiscovery, scan_network_ports
from monitor import NetworkMonitor, TelegramNotifier
import cloud_uploader as cloud_uploader_module
from cloud_uploader import init_cloud_uploader

app = Flask(__name__)

# Endpoint to expose all RTSP URLs for automation (MediaMTX integration)
@app.route('/api/streams', methods=['GET'])
def api_streams():
    """Return all camera RTSP URLs and metadata as JSON."""
    streams = config.get('streams', [])
    # Return id, name, rtsp_url for each camera
    return jsonify({
        'streams': [
            {
                'id': s.get('id'),
                'name': s.get('name'),
                'rtsp_url': s.get('rtsp_url')
            } for s in streams if s.get('enabled', True)
        ]
    })

# Global state
config = {}
config_file = Path('config.yaml')
streamers = {}  # stream_id -> Streamer instance
network_monitor = None
telegram_notifier = None
discovery = ONVIFDiscovery()

def load_config():
    """Load configuration from YAML file"""
    global config
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
    else:
        # Create default config
        config = {
            'normal_resolution': '1280x720',
            'low_resolution': '640x360',
            'motion_sensitivity': 25,
            'motion_min_area': 500,
            'motion_cooldown': 10,
            'motion_low_fps': 1,
            'motion_high_fps': 25,
            'motion_zones': [],
            'upload_speed_threshold_mbps': 2,
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'streams': [],
            'web_port': 5000,
            'web_host': '0.0.0.0'
        }
        save_config()
    return config

def save_config():
    """Save configuration to YAML file"""
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def init_services():
    """Initialize background services"""
    global network_monitor, telegram_notifier
    
    # Network monitor
    threshold = config.get('upload_speed_threshold_mbps', 2)
    network_monitor = NetworkMonitor(threshold_mbps=threshold)
    network_monitor.start()
    
    # Telegram notifier
    bot_token = config.get('telegram_bot_token', '')
    chat_id = config.get('telegram_chat_id', '')
    telegram_notifier = TelegramNotifier(bot_token, chat_id)
    
    # Cloud uploader
    uploader = init_cloud_uploader(config)
    if uploader.enabled:
        print(f"Cloud upload enabled: {uploader.server_url}")
        # Start upload queue processor
        threading.Thread(target=process_upload_queue, daemon=True).start()
    else:
        print("Cloud upload disabled (configure cloud_upload_url, cloud_username, cloud_password)")
    
    # Start network quality monitor thread
    threading.Thread(target=monitor_network_quality, daemon=True).start()
    
    # Start existing streams
    for stream in config.get('streams', []):
        if stream.get('enabled', True):
            start_stream(stream)

def monitor_network_quality():
    """Monitor network quality and adjust stream quality"""
    global network_monitor, telegram_notifier
    
    was_slow = False
    
    while True:
        try:
            time.sleep(10)  # Check every 10 seconds
            
            if network_monitor:
                status = network_monitor.get_status()
                is_slow = status['is_slow']
                
                # State changed
                if is_slow and not was_slow:
                    print("Network is slow, switching to low quality mode")
                    Streamer.set_low_quality(True)
                    
                    # Send Telegram alert
                    if telegram_notifier:
                        telegram_notifier.send_network_slow_alert(
                            status['upload_mbps'],
                            status['threshold_mbps']
                        )
                
                elif not is_slow and was_slow:
                    print("Network recovered, switching to normal quality")
                    Streamer.set_low_quality(False)
                    
                    # Send Telegram alert
                    if telegram_notifier:
                        telegram_notifier.send_network_recovered_alert(
                            status['upload_mbps']
                        )
                
                was_slow = is_slow
                
        except Exception as e:
            print(f"Network quality monitor error: {e}")
            time.sleep(5)

def process_upload_queue():
    """Process cloud upload queue continuously"""
    print("Upload queue processor thread started")
    while True:
        try:
            uploader = cloud_uploader_module.cloud_uploader
            if uploader and uploader.enabled:
                status = uploader.get_queue_status()
                if status['queue_size'] > 0:
                    print(f"Processing upload queue ({status['queue_size']} items)...")
                uploader.process_queue()
            time.sleep(2)  # Process every 2 seconds
        except Exception as e:
            print(f"Upload queue processor error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)

def start_stream(stream):
    """Start a stream"""
    stream_id = stream['id']
    
    # Stop existing stream if running
    if stream_id in streamers:
        streamers[stream_id].stop()
        del streamers[stream_id]
    
    try:
        # Create streamer with per-stream config
        streamer_config = config.copy()
        # Merge per-stream chunking/streaming settings
        for key in ['streaming_enabled', 'chunking_enabled', 'chunk_duration', 'chunk_fps']:
            if key in stream:
                streamer_config[key] = stream[key]

        # For MediaMTX relay, just use RTSP URL
        streamer = Streamer(
            rtsp_url=stream['rtsp_url'],
            config=streamer_config,
            stream_id=stream_id
        )
        streamers[stream_id] = streamer
        print(f"Started stream: {stream_id} - {stream['name']} -> {stream['rtsp_url']}")
    except Exception as e:
        print(f"Failed to start stream {stream_id}: {e}")

def stop_stream(stream_id):
    """Stop a stream"""
    if stream_id in streamers:
        streamers[stream_id].stop()
        del streamers[stream_id]
        print(f"Stopped stream: {stream_id}")

# ==================== Web Routes ====================

@app.route('/')
def index():
    """Dashboard page"""
    return render_template('index.html', 
                         streams=config.get('streams', []),
                         config=config)

@app.route('/discover')
def discover_page():
    """ONVIF discovery page"""
    return render_template('discover.html')

@app.route('/motion')
def motion_page():
    """Motion settings page"""
    return render_template('motion.html',
                         sensitivity=config.get('motion_sensitivity', 25),
                         min_area=config.get('motion_min_area', 500),
                         cooldown=config.get('motion_cooldown', 10),
                         zones=config.get('motion_zones', []))

@app.route('/motion_log')
def motion_log_page():
    """Motion event log page"""
    # Collect logs from all streams (from JSON event files)
    all_logs = []
    log_dir = Path('logs')
    
    if log_dir.exists():
        for event_file in log_dir.glob('events_*.json'):
            try:
                with open(event_file, 'r') as f:
                    events = json.load(f)
                    stream_id = event_file.stem.replace('events_', '')
                    # Get all events for scrolling
                    for event in events:
                        # Format: "2025-11-23 14:15:16 - MOTION - FPS: 25"
                        timestamp = event['timestamp'].replace('T', ' ').split('.')[0]
                        line = f"{timestamp} - {event['status']} - FPS: {event['fps']}"
                        all_logs.append({
                            'stream': stream_id,
                            'line': line
                        })
            except:
                pass
    
    # Sort by timestamp (most recent first)
    all_logs.sort(key=lambda x: x['line'], reverse=True)
    
    return render_template('motion_log.html', logs=all_logs)

# ==================== API Routes ====================

@app.route('/api/discover', methods=['POST'])
def api_discover():
    """Start ONVIF discovery"""
    try:
        cameras = discovery.discover_cameras(timeout=5)
        
        # Filter out cameras that are already added
        existing_ips = set()
        for stream in config.get('streams', []):
            # Extract IP from RTSP URL
            import re
            match = re.search(r'@?(\d+\.\d+\.\d+\.\d+)', stream.get('rtsp_url', ''))
            if match:
                existing_ips.add(match.group(1))
        
        # Filter cameras
        filtered_cameras = [cam for cam in cameras if cam['ip'] not in existing_ips]
        
        return jsonify({
            'success': True,
            'cameras': filtered_cameras,
            'count': len(filtered_cameras),
            'filtered_count': len(cameras) - len(filtered_cameras)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scan_network', methods=['POST'])
def api_scan_network():
    """Scan network for cameras"""
    try:
        data = request.json
        subnet = data.get('subnet', '192.168.1')
        port = data.get('port', 80)
        
        ips = scan_network_ports(port=port, subnet=subnet)
        
        return jsonify({
            'success': True,
            'ips': ips,
            'count': len(ips)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test_stream', methods=['POST'])
def api_test_stream():
    """Test camera stream with credentials"""
    try:
        data = request.json
        rtsp_url = data.get('rtsp_url')
        
        if not rtsp_url:
            return jsonify({'success': False, 'error': 'No RTSP URL provided'}), 400
        
        import cv2
        
        # Test RTSP connection with more lenient settings
        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10 second timeout
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        is_valid = False
        error_msg = None
        
        if cap.isOpened():
            # Try to read a frame but don't fail if first frame is problematic
            ret, frame = cap.read()
            if ret and frame is not None:
                is_valid = True
            else:
                # Give it another chance
                time.sleep(0.5)
                ret, frame = cap.read()
                is_valid = ret and frame is not None
                if not is_valid:
                    error_msg = 'Could not read frame from camera'
            cap.release()
        else:
            error_msg = 'Could not open RTSP stream'
        
        print(f"[TEST_STREAM] {rtsp_url} - Valid: {is_valid}, Error: {error_msg}")
        
        return jsonify({
            'success': True,
            'valid': is_valid,
            'error': error_msg
        })
    except Exception as e:
        print(f"[TEST_STREAM] Exception: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream_proxy')
def api_stream_proxy():
    """Proxy RTSP stream as MJPEG"""
    rtsp_url = request.args.get('rtsp_url')
    
    if not rtsp_url:
        return "No RTSP URL provided", 400
    
    import cv2
    
    def generate():
        print(f"[STREAM_PROXY] Starting stream for: {rtsp_url}")
        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)  # 15 second timeout
        
        if not cap.isOpened():
            print(f"[STREAM_PROXY] Failed to open stream: {rtsp_url}")
            return
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Encode frame as JPEG
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ret:
                    continue
                
                # Yield frame in multipart format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        finally:
            cap.release()
    
    return app.response_class(generate(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/add_stream', methods=['POST'])
def api_add_stream():
    """Add a new stream"""
    try:
        data = request.json
        rtsp_url = data.get('rtsp_url', '')
        
        if not rtsp_url:
            return jsonify({'success': False, 'error': 'RTSP URL is required'}), 400

        # The rtsp_url should already have credentials embedded from ONVIF or manual entry
        # Test the stream before adding
        import cv2
        print(f"[ADD_STREAM] Testing RTSP URL: {rtsp_url[:30]}...")
        
        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10 second timeout
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        valid = False
        error_msg = None
        
        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                valid = True
                print(f"[ADD_STREAM] Stream validation successful")
            else:
                # Give it another try
                time.sleep(0.5)
                ret, frame = cap.read()
                valid = ret and frame is not None
                if not valid:
                    error_msg = 'Could not read frame from camera'
                    print(f"[ADD_STREAM] Failed to read frame")
            cap.release()
        else:
            error_msg = 'Could not open RTSP stream - check credentials and network'
            print(f"[ADD_STREAM] Failed to open stream")

        if not valid:
            return jsonify({'success': False, 'error': error_msg or 'Invalid RTSP stream'}), 400

        # Use provided camera ID or generate one
        stream_id = data.get('id') or f"cam{len(config.get('streams', [])) + 1}"

        stream = {
            'id': stream_id,
            'name': data.get('name', f'Camera {stream_id}'),
            'rtsp_url': rtsp_url,
            'enabled': True,
            'streaming_enabled': data.get('streaming_enabled', True),
            'chunking_enabled': data.get('chunking_enabled', False),
            'chunk_duration': int(data.get('chunk_duration', 5)),
            'chunk_fps': int(data.get('chunk_fps', 2))
        }

        # Add to config
        if 'streams' not in config:
            config['streams'] = []
        config['streams'].append(stream)
        save_config()

        # Start stream
        start_stream(stream)
        
        print(f"[ADD_STREAM] Successfully added stream: {stream_id}")

        return jsonify({
            'success': True,
            'stream': stream
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/remove_stream', methods=['POST'])
def api_remove_stream():
    """Remove a stream"""
    try:
        data = request.get_json(force=True)
        if not data or 'stream_id' not in data:
            return jsonify({'success': False, 'error': 'stream_id required'}), 400

        stream_id = data['stream_id']

        # Stop stream (no-op if not running)
        try:
            stop_stream(stream_id)
        except Exception as e:
            # Log and continue removing from config
            print(f"Error stopping stream {stream_id}: {e}")

        # Remove from config
        streams = config.get('streams', []) or []
        new_streams = [s for s in streams if s.get('id') != stream_id]
        if len(new_streams) == len(streams):
            # stream id wasn't found in config -> return 404
            return jsonify({'success': False, 'error': 'stream not found'}), 404

        config['streams'] = new_streams
        save_config()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/toggle_stream', methods=['POST'])
def api_toggle_stream():
    """Enable/disable a stream"""
    try:
        data = request.get_json(force=True)
        if not data or 'stream_id' not in data or 'enabled' not in data:
            return jsonify({'success': False, 'error': 'stream_id and enabled required'}), 400

        stream_id = data['stream_id']
        enabled = bool(data['enabled'])

        # Find stream in config
        found = False
        for stream in config.get('streams', []):
            if stream.get('id') == stream_id:
                found = True
                stream['enabled'] = enabled

                if enabled:
                    try:
                        start_stream(stream)
                    except Exception as e:
                        return jsonify({'success': False, 'error': f'failed to start stream: {e}'}), 500
                else:
                    try:
                        stop_stream(stream_id)
                    except Exception as e:
                        # stopping should be best-effort
                        print(f"Error stopping stream {stream_id}: {e}")
                break

        if not found:
            return jsonify({'success': False, 'error': 'stream not found'}), 404

        save_config()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/network_status')
def api_network_status():
    """Get network status"""
    if network_monitor:
        status = network_monitor.get_status()
        status['history'] = network_monitor.get_history(minutes=5)
        return jsonify(status)
    return jsonify({'error': 'Monitor not running'}), 500

@app.route('/api/motion_status')
def api_motion_status():
    """Get motion status for all streams"""
    status = {}
    for stream_id, streamer in streamers.items():
        status[stream_id] = {
            'active': streamer.motion_active,
            'fps': streamer._get_target_fps()
        }
    return jsonify(status)

@app.route('/api/cloud_upload_status')
def api_cloud_upload_status():
    """Get cloud upload status"""
    uploader = cloud_uploader_module.cloud_uploader
    if uploader:
        status = uploader.get_queue_status()
        status['server_url'] = uploader.server_url if uploader.enabled else None
        return jsonify(status)
    return jsonify({'enabled': False, 'authenticated': False, 'queue_size': 0})

@app.route('/api/save_zones', methods=['POST'])
def api_save_zones():
    """Save motion detection zones"""
    try:
        data = request.json
        zones = [[z['x'], z['y'], z['w'], z['h']] for z in data['zones']]
        
        config['motion_zones'] = zones
        save_config()
        
        # Update all streamers
        Streamer.restart_all()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save_motion_config', methods=['POST'])
def api_save_motion_config():
    """Save motion detection configuration"""
    try:
        data = request.json
        
        config['motion_sensitivity'] = int(data['sensitivity'])
        config['motion_min_area'] = int(data['min_area'])
        config['motion_cooldown'] = int(data['cooldown'])
        save_config()
        
        # Update all streamers
        for streamer in streamers.values():
            streamer.update_config(config)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_motion_events')
def api_get_motion_events():
    """Get motion events for all streams"""
    events = {}
    log_dir = Path('logs')
    
    if log_dir.exists():
        for event_file in log_dir.glob('events_*.json'):
            try:
                with open(event_file, 'r') as f:
                    stream_id = event_file.stem.replace('events_', '')
                    events[stream_id] = json.load(f)
            except:
                pass
    
    return jsonify(events)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    if request.method == 'GET':
        return jsonify(config)
    
    try:
        data = request.json
        # Update config
        for key, value in data.items():
            if key in config:
                config[key] = value
        # Update per-stream settings if present
        if 'streams' in data:
            config['streams'] = data['streams']
            # Restart all streams with new settings
            for stream in config['streams']:
                if stream.get('enabled', True):
                    start_stream(stream)
                else:
                    stop_stream(stream['id'])
        save_config()
        # Restart services if needed
        if 'upload_speed_threshold_mbps' in data:
            if network_monitor:
                network_monitor.set_threshold(data['upload_speed_threshold_mbps'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# ==================== Chunk Event API ====================

@app.route('/api/chunk_events')
def api_chunk_events():
    """Return recent chunk events (filenames) for all streams."""
    events = {}
    chunk_dir = Path('tmp/chunks')
    if chunk_dir.exists():
        for chunk_file in sorted(chunk_dir.glob('*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True)[:20]:
            stream_id = chunk_file.name.split('_')[0]
            if stream_id not in events:
                events[stream_id] = []
            events[stream_id].append(chunk_file.name)
    return jsonify(events)

@app.route('/api/change_camera_id', methods=['POST'])
def api_change_camera_id():
    """Change camera ID for a stream"""
    try:
        data = request.json
        old_id = data.get('old_id')
        new_id = data.get('new_id')
        if not old_id or not new_id:
            return jsonify({'success': False, 'error': 'Missing old_id or new_id'}), 400
        # Check for duplicate
        for s in config.get('streams', []):
            if s['id'] == new_id:
                return jsonify({'success': False, 'error': 'Camera ID already exists'}), 400
        # Find and update
        found = False
        for s in config.get('streams', []):
            if s['id'] == old_id:
                s['id'] = new_id
                found = True
                break
        if not found:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404
        save_config()
        # Also update running streamer
        if old_id in streamers:
            streamers[new_id] = streamers.pop(old_id)
            streamers[new_id].id = new_id
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_local_subnet', methods=['GET'])
def api_get_local_subnet():
    """Get the local subnet prefix for auto-populating discovery"""
    try:
        import socket
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Extract subnet (first 3 octets)
        subnet = '.'.join(local_ip.split('.')[:3])
        return jsonify({'success': True, 'subnet': subnet, 'local_ip': local_ip})
    except Exception as e:
        print(f"[Subnet] Error detecting local subnet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/onvif_rtsp_uri', methods=['POST'])
def api_onvif_rtsp_uri():
    """Get RTSP URI from ONVIF using credentials"""
    try:
        data = request.json
        ip = data.get('ip')
        port = int(data.get('port', 80))
        username = data.get('username', '')
        password = data.get('password', '')
        
        if not ip or not username or not password:
            print(f"[ONVIF] Missing required fields: ip={ip}, username={'set' if username else 'missing'}, password={'set' if password else 'missing'}")
            return jsonify({'success': False, 'error': 'Missing required fields (IP, username, or password)'}), 400
        
        print(f"[ONVIF] Attempting RTSP URI retrieval for {ip}:{port} with user '{username}'")
        info = discovery.get_camera_info(ip, port, username, password)
        
        # Check for errors
        if info and 'error' in info:
            error_type = info['error']
            message = info['message']
            print(f"[ONVIF] Error: {error_type} - {message}")
            
            # Return appropriate HTTP status code
            if error_type == 'auth':
                return jsonify({'success': False, 'error': 'Authentication failed. Check username and password.'}), 401
            else:
                return jsonify({'success': False, 'error': message}), 500
        
        # Check for stream URIs
        if info and info.get('stream_uris') and len(info['stream_uris']) > 0:
            rtsp_url = info['stream_uris'][0]
            print(f"[ONVIF] RTSP URI found: {rtsp_url[:50]}...")
            return jsonify({
                'success': True, 
                'rtsp_url': rtsp_url,
                'manufacturer': info.get('manufacturer', 'Unknown'),
                'model': info.get('model', 'Unknown')
            })
        else:
            print(f"[ONVIF] No RTSP URIs found for {ip}:{port}")
            return jsonify({
                'success': False, 
                'error': 'Could not retrieve RTSP URI from camera. Camera may not support ONVIF properly.'
            }), 500
            
    except Exception as e:
        import traceback
        print(f"[ONVIF] Exception: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error connecting to camera: {str(e)}'}), 500

# ==================== Main ====================

if __name__ == '__main__':
    print("=" * 60)
    print("Edge Agent - Motion-Triggered Video Streaming")
    print("=" * 60)
    
    # Load config
    load_config()
    print(f"Configuration loaded from {config_file}")
    
    # Initialize services
    init_services()
    print("Services initialized")
    
    # Get web server settings
    host = config.get('web_host', '0.0.0.0')
    port = config.get('web_port', 5000)
    
    print(f"\nWeb UI available at: http://localhost:{port}")
    print("=" * 60)
    
    # Run Flask app
    app.run(host=host, port=port, debug=False, threaded=True)