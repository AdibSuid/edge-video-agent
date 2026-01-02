#!/usr/bin/env python3
"""
Verify RTSP authentication and pipeline configuration
"""

import yaml
import sys

print("=" * 60)
print("RTSP Authentication Verification")
print("=" * 60)

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print("\n✓ Config loaded successfully")
print(f"✓ Hardware pipeline enabled: {config.get('use_hardware_pipeline', False)}")
print(f"✓ Hardware decode enabled: {config.get('use_hardware_decode', False)}")
print(f"✓ Hardware encode enabled: {config.get('use_hardware_encode', False)}")

print("\n" + "=" * 60)
print("Configured Streams:")
print("=" * 60)

for stream in config['streams']:
    if not stream.get('enabled', True):
        continue
    
    stream_id = stream['id']
    rtsp_url = stream['rtsp_url']
    
    print(f"\n{stream_id}: {stream['name']}")
    print(f"  URL: {rtsp_url}")
    
    # Check if authentication is present
    if '@' in rtsp_url:
        # Extract credentials
        protocol_end = rtsp_url.find('//') + 2
        at_pos = rtsp_url.find('@', protocol_end)
        
        if at_pos > 0:
            creds = rtsp_url[protocol_end:at_pos]
            if ':' in creds:
                print(f"  ✓ Authentication: Present (username:password)")
            else:
                print(f"  ⚠ Authentication: Partial (username only)")
        else:
            print(f"  ✗ Authentication: Missing")
    else:
        print(f"  ✗ Authentication: Missing")
    
    print(f"  Chunking: {'Enabled' if stream.get('chunking_enabled') else 'Disabled'}")
    print(f"  Chunk duration: {stream.get('chunk_duration', 5)}s")

print("\n" + "=" * 60)
print("GStreamer Pipeline Test Command:")
print("=" * 60)

# Get first enabled stream
first_stream = None
for stream in config['streams']:
    if stream.get('enabled', True):
        first_stream = stream
        break

if first_stream:
    rtsp_url = first_stream['rtsp_url']
    print(f"\nTest with: ./test_auth_pipeline.sh")
    print(f"\nOr manually:")
    print(f'gst-launch-1.0 -v rtspsrc location="{rtsp_url}" protocols=tcp ! fakesink')
    print("\n✓ Ready to test!")
else:
    print("\n⚠ No enabled streams found!")

print("\n" + "=" * 60)
