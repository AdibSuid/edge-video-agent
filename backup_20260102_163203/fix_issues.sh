#!/bin/bash

echo "=== Fixing Edge Video Agent Issues ==="

# 1. Update config.yaml - disable cloud upload temporarily
cat > config_backup.yaml << 'EOF'
# Backup of original config
EOF
cp config.yaml config_backup.yaml

# Update config to disable cloud upload
python3 << 'PYTHON'
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Disable cloud upload to stop authentication errors
config['cloud_upload_enabled'] = False

# Improve motion detection settings for Jetson
config['motion_detection_scale'] = 0.25
config['motion_blur_kernel'] = 5
config['motion_frame_skip'] = 2

# Use hardware decode
config['use_hardware_decode'] = True
config['encoding_preset'] = 'ultrafast'
config['encoding_crf'] = 28

with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print("✓ Config updated")
PYTHON

echo ""
echo "=== Testing Camera Connectivity ==="

# Test each camera RTSP URL
python3 << 'PYTHON'
import yaml
import subprocess
import sys

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

streams = config.get('streams', [])

if not streams:
    print("No cameras configured")
    sys.exit(0)

for stream in streams:
    rtsp_url = stream.get('rtsp_url')
    name = stream.get('name', stream.get('id'))
    
    print(f"\nTesting {name}...")
    print(f"  URL: {rtsp_url[:50]}...")
    
    # Test with ffprobe
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-rtsp_transport', 'tcp',
        '-i', rtsp_url,
        '-show_entries', 'stream=codec_name,width,height',
        '-of', 'default=noprint_wrappers=1'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            print(f"  ✓ Camera is reachable")
            print(result.stdout.decode('utf-8', errors='ignore')[:200])
        else:
            print(f"  ✗ Camera connection failed")
            print(f"  Error: {result.stderr.decode('utf-8', errors='ignore')[:200]}")
    except subprocess.TimeoutExpired:
        print(f"  ✗ Connection timeout (>10s)")
    except Exception as e:
        print(f"  ✗ Error: {e}")

PYTHON

echo ""
echo "=== Recommendations ==="
echo "1. Cloud upload disabled - re-enable when server is back online"
echo "2. Check camera network connectivity"
echo "3. Verify RTSP URLs are correct"
echo "4. Restart the application"