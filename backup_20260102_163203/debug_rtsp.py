#!/usr/bin/env python3
"""
Debug RTSP connection - test different methods
"""

import subprocess
import sys

def test_with_opencv(rtsp_url):
    """Test with OpenCV (simplest)"""
    print("="*70)
    print("1. Testing with OpenCV")
    print("="*70)
    
    try:
        import cv2
        print(f"Opening: {rtsp_url}")
        
        cap = cv2.VideoCapture(rtsp_url)
        
        if cap.isOpened():
            print("✓ OpenCV can open stream!")
            
            # Try to read a frame
            ret, frame = cap.read()
            if ret:
                print(f"✓ Can read frames! Shape: {frame.shape}")
                cap.release()
                return True
            else:
                print("✗ Cannot read frames")
                cap.release()
                return False
        else:
            print("✗ OpenCV cannot open stream")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_with_ffplay(rtsp_url):
    """Test if ffplay can play it"""
    print("\n" + "="*70)
    print("2. Testing with ffplay (will play for 5 seconds)")
    print("="*70)
    print("Close the window or wait 5 seconds...")
    
    cmd = [
        'ffplay',
        '-rtsp_transport', 'tcp',
        '-i', rtsp_url,
        '-t', '5'
    ]
    
    try:
        result = subprocess.run(cmd, timeout=10)
        if result.returncode == 0:
            print("\n✓ ffplay worked!")
            return True
        else:
            print("\n✗ ffplay failed")
            return False
    except subprocess.TimeoutExpired:
        print("\n✓ ffplay worked (timeout ok)")
        return True
    except FileNotFoundError:
        print("\n⚠ ffplay not installed")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_gstreamer_verbose(rtsp_url):
    """Test GStreamer with verbose output to see exact error"""
    print("\n" + "="*70)
    print("3. Testing GStreamer (verbose)")
    print("="*70)
    
    cmd = [
        'gst-launch-1.0',
        '--gst-debug=rtspsrc:4',  # Verbose RTSP debugging
        'rtspsrc', f'location={rtsp_url}',
        'protocols=tcp',
        'latency=200',
        '!', 'fakesink'
    ]
    
    print("Running with verbose output...")
    print("(Will timeout after 10s - that's OK if we see connection)\n")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout + result.stderr
        
        # Look for specific errors
        if 'Unauthorized' in output or '401' in output:
            print("✗ Authentication failed (wrong username/password)")
            return False, 'auth'
        elif 'Not Found' in output or '404' in output:
            print("✗ Stream path not found (wrong URL path)")
            return False, 'path'
        elif 'Connection refused' in output:
            print("✗ Connection refused (camera not accepting connections)")
            return False, 'refused'
        elif 'Could not connect' in output:
            print("✗ Could not connect (network issue)")
            return False, 'network'
        elif 'Forbidden' in output or '403' in output:
            print("✗ Access forbidden")
            return False, 'forbidden'
        elif 'PLAY' in output and 'OK' in output:
            print("✓ GStreamer connected successfully!")
            return True, 'ok'
        else:
            print("✗ Unknown error. Debug output:")
            # Show relevant lines
            for line in output.split('\n'):
                if any(word in line.lower() for word in ['error', 'warn', 'fail', 'unauthorized', 'rtsp']):
                    print(f"  {line.strip()}")
            return False, 'unknown'
            
    except subprocess.TimeoutExpired:
        print("✓ Timeout reached - but that might mean it's working!")
        print("  (GStreamer connected but we stopped it)")
        return True, 'timeout'
    except Exception as e:
        print(f"✗ Error: {e}")
        return False, 'error'

def test_different_url_formats(base_url):
    """Try different URL format variations"""
    print("\n" + "="*70)
    print("4. Testing URL Format Variations")
    print("="*70)
    
    # Extract components
    import re
    
    # Parse URL: rtsp://user:pass@ip:port/path?params
    match = re.match(r'rtsp://([^:]+):([^@]+)@([^:]+):(\d+)(/[^?]+)(\?.*)?', base_url)
    
    if not match:
        print("Could not parse URL")
        return []
    
    user, pwd, ip, port, path, params = match.groups()
    params = params or ''
    
    print(f"Parsed URL:")
    print(f"  User: {user}")
    print(f"  Pass: {pwd}")
    print(f"  IP:   {ip}")
    print(f"  Port: {port}")
    print(f"  Path: {path}")
    print(f"  Params: {params}")
    
    # Try variations
    variations = [
        f"rtsp://{user}:{pwd}@{ip}:{port}{path}{params}",  # Original
        f"rtsp://{ip}:{port}{path}{params}",  # Without auth in URL
        f"rtsp://{user}:{pwd}@{ip}{path}{params}",  # Without port
        f"rtsp://{ip}{path}{params}",  # Minimal
    ]
    
    working = []
    
    for i, url in enumerate(variations, 1):
        print(f"\nVariation {i}: {url}")
        
        cmd = [
            'ffprobe',
            '-rtsp_transport', 'tcp',
            '-v', 'error',
            '-i', url,
            '-show_streams'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if 'codec_name' in result.stdout or 'Stream' in result.stderr:
                print(f"  ✓ This format works!")
                working.append(url)
            else:
                print(f"  ✗ Failed")
        except:
            print(f"  ✗ Error/Timeout")
    
    return working

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_rtsp.py '<RTSP_URL>'")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              RTSP Connection Debugger                           ║
╚══════════════════════════════════════════════════════════════════╝

Testing different methods to connect to your camera...
""")
    
    print(f"RTSP URL: {rtsp_url}\n")
    
    # Run tests
    results = {}
    
    results['opencv'] = test_with_opencv(rtsp_url)
    results['ffplay'] = test_with_ffplay(rtsp_url)
    
    gst_success, gst_error = test_gstreamer_verbose(rtsp_url)
    results['gstreamer'] = gst_success
    
    working_urls = test_different_url_formats(rtsp_url)
    
    # Summary
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"OpenCV:     {'✓ WORKS' if results['opencv'] else '✗ FAILED'}")
    print(f"ffplay:     {'✓ WORKS' if results['ffplay'] else '✗ FAILED'}")
    print(f"GStreamer:  {'✓ WORKS' if results['gstreamer'] else f'✗ FAILED ({gst_error})'}")
    
    if working_urls:
        print(f"\nWorking URL formats: {len(working_urls)}")
        for url in working_urls:
            print(f"  ✓ {url}")
    
    # Diagnosis
    print("\n" + "="*70)
    print("DIAGNOSIS")
    print("="*70)
    
    if results['opencv']:
        print("\n✅ GOOD NEWS: OpenCV can read the stream!")
        print("\nYour application should work with:")
        print("```python")
        print(f"cap = cv2.VideoCapture('{rtsp_url}')")
        print("ret, frame = cap.read()")
        print("```")
        print("\nNo need for complex GStreamer pipelines!")
        
    elif gst_error == 'auth':
        print("\n❌ Authentication problem")
        print("Fix: Check username and password in camera settings")
        
    elif gst_error == 'path':
        print("\n❌ Wrong RTSP path")
        print("Fix: Check camera manual for correct RTSP URL")
        print("Common paths:")
        print("  - /cam/realmonitor?channel=1&subtype=0")
        print("  - /stream1")
        print("  - /h264")
        print("  - /live/ch00_0")
        
    elif gst_error == 'refused':
        print("\n❌ Camera refusing connections")
        print("Fix:")
        print("  1. Check camera is on and responding")
        print("  2. Verify RTSP service is enabled in camera")
        print("  3. Check firewall settings")
        
    else:
        print("\n⚠ Cannot determine exact issue")
        print("\nSince VLC works, try:")
        print("1. Use OpenCV directly (simplest):")
        print(f"   cap = cv2.VideoCapture('{rtsp_url}')")
        print("\n2. Or FFmpeg:")
        print(f"   ffmpeg -rtsp_transport tcp -i '{rtsp_url}' ...")
        print("\n3. GStreamer might have compatibility issues with this camera")
    
    print()

if __name__ == "__main__":
    main()
