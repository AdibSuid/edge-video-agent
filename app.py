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

app = Flask(__name__)

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
            'cloud_srt_host': 'srt://your-cloud-server:9000',
            'srt_passphrase': 'your-secure-passphrase-here',
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
        streamer = Streamer(
            rtsp_url=stream['rtsp_url'],
            srt_url=config['cloud_srt_host'],
            passphrase=config['srt_passphrase'],
            config=streamer_config,
            stream_id=stream_id
        )
        streamers[stream_id] = streamer
        print(f"Started stream: {stream_id} - {stream['name']}")
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

@app.route('/add_manual')
def add_manual_page():
    """Manual camera add page"""
    return render_template('add_manual.html')

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
    # Collect logs from all streams
    all_logs = []
    log_dir = Path('logs')
    
    if log_dir.exists():
        for log_file in log_dir.glob('motion_*.log'):
            try:
                with open(log_file, 'r') as f:
                    logs = f.readlines()[-50:]  # Last 50 lines
                    all_logs.extend([{
                        'stream': log_file.stem.replace('motion_', ''),
                        'line': line.strip()
                    } for line in logs])
            except:
                pass
    
    return render_template('motion_log.html', logs=all_logs)

# ==================== API Routes ====================

@app.route('/api/discover', methods=['POST'])
def api_discover():
    """Start ONVIF discovery"""
    try:
        cameras = discovery.discover_cameras(timeout=5)
        return jsonify({
            'success': True,
            'cameras': cameras,
            'count': len(cameras)
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

@app.route('/api/test_rtsp', methods=['POST'])
def api_test_rtsp():
    """Test RTSP URL"""
    try:
        data = request.json
        rtsp_url = data.get('rtsp_url')
        
        is_valid = discovery.test_rtsp_url(rtsp_url)
        
        return jsonify({
            'success': True,
            'valid': is_valid
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/add_stream', methods=['POST'])
def api_add_stream():
    """Add a new stream"""
    try:
        data = request.json
        
        # Generate stream ID
        stream_id = f"cam{len(config.get('streams', [])) + 1}"
        
        stream = {
            'id': stream_id,
            'name': data.get('name', f'Camera {stream_id}'),
            'rtsp_url': data['rtsp_url'],
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