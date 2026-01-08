#!/usr/bin/env python3
"""
Test RTSP stream accessibility first before testing decoders
"""

import subprocess
import sys

def test_rtsp_basic(rtsp_url):
    """Test if RTSP stream is accessible at all"""
    print("="*70)
    print("1. Testing RTSP Stream Accessibility")
    print("="*70)
    print(f"RTSP URL: {rtsp_url}\n")
    
    # Test with ffprobe
    print("Testing with ffprobe...")
    cmd = ['ffprobe', '-v', 'error', '-show_streams', '-i', rtsp_url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if 'codec_name=h264' in result.stdout or 'Stream #0' in result.stderr:
            print("✓ RTSP stream is accessible")
            
            # Show stream info
            for line in result.stdout.split('\n') + result.stderr.split('\n'):
                if any(word in line for word in ['codec', 'width', 'height', 'fps', 'Stream']):
                    print(f"  {line.strip()}")
            
            return True
        else:
            print("✗ Stream not accessible or no video stream found")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT - Stream not responding")
        return False
    except FileNotFoundError:
        print("⚠ ffprobe not found, trying alternative...")
        return test_rtsp_with_gstreamer(rtsp_url)
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_rtsp_with_gstreamer(rtsp_url):
    """Test RTSP with basic GStreamer pipeline"""
    print("\nTesting with GStreamer (basic)...")
    
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=10', '!',
        'fakesink'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ GStreamer can connect to stream")
            return True
        else:
            print("✗ GStreamer cannot connect")
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if 'error' in line.lower() or 'could not' in line.lower():
                        print(f"  {line.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_rtsp_depay(rtsp_url):
    """Test if we can depayload the H.264 stream"""
    print("\n" + "="*70)
    print("2. Testing H.264 Depayload")
    print("="*70)
    
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=30', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'fakesink'
    ]
    
    print("Testing depayload pipeline...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ H.264 depayload successful")
            return True
        else:
            print("✗ Depayload failed")
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if 'error' in line.lower():
                        print(f"  {line.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_simple_software_decode(rtsp_url):
    """Test simplest software decode"""
    print("\n" + "="*70)
    print("3. Testing Software Decoder (Simplest)")
    print("="*70)
    
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=30', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'avdec_h264', '!',
        'fakesink'
    ]
    
    print("Testing software decode...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✓ Software decode successful")
            return True
        else:
            print("✗ Software decode failed")
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if 'error' in line.lower():
                        print(f"  {line.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def check_network_connection(rtsp_url):
    """Check if camera IP is reachable"""
    print("\n" + "="*70)
    print("4. Network Connectivity Check")
    print("="*70)
    
    # Extract IP from URL
    import re
    match = re.search(r'@([0-9.]+):', rtsp_url)
    if not match:
        match = re.search(r'//([0-9.]+):', rtsp_url)
    
    if match:
        ip = match.group(1)
        print(f"Camera IP: {ip}")
        
        # Ping test
        cmd = ['ping', '-c', '3', ip]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                print(f"✓ Camera {ip} is reachable")
                return True
            else:
                print(f"✗ Camera {ip} is NOT reachable")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"✗ Ping timeout to {ip}")
            return False
        except Exception as e:
            print(f"⚠ Could not ping: {e}")
            return False
    else:
        print("⚠ Could not extract IP from URL")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_rtsp_stream.py '<RTSP_URL>'")
        print("\nExample:")
        print("  python check_rtsp_stream.py 'rtsp://admin:pass@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0'")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              RTSP Stream Diagnostic Tool                        ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    print(f"\nDiagnosing: {rtsp_url}\n")
    
    # Run diagnostics
    results = {}
    
    results['network'] = check_network_connection(rtsp_url)
    results['rtsp_basic'] = test_rtsp_basic(rtsp_url)
    results['depayload'] = test_rtsp_depay(rtsp_url)
    results['software_decode'] = test_simple_software_decode(rtsp_url)
    
    # Summary
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)
    
    for test_name, result in results.items():
        status = "✓ OK" if result else "✗ FAILED"
        print(f"  {test_name:20s}: {status}")
    
    print("\n" + "="*70)
    print("VERDICT")
    print("="*70)
    
    if not results['network']:
        print("\n❌ PROBLEM: Camera is not reachable on network")
        print("\nPossible causes:")
        print("  1. Camera is offline or powered off")
        print("  2. Wrong IP address")
        print("  3. Network connectivity issue")
        print("\nFix:")
        print("  - Verify camera is powered on")
        print("  - Check camera IP in browser or with ping")
        print("  - Verify network connection")
        
    elif not results['rtsp_basic']:
        print("\n❌ PROBLEM: RTSP stream is not accessible")
        print("\nPossible causes:")
        print("  1. Wrong RTSP URL or path")
        print("  2. Wrong credentials")
        print("  3. Camera RTSP service not running")
        print("  4. Firewall blocking port 554")
        print("\nFix:")
        print("  - Verify RTSP URL in camera settings")
        print("  - Check username/password")
        print("  - Test with: ffplay '<your-rtsp-url>'")
        
    elif not results['depayload']:
        print("\n❌ PROBLEM: Cannot depayload H.264 stream")
        print("\nPossible causes:")
        print("  1. Stream is not H.264")
        print("  2. Corrupted stream")
        print("\nFix:")
        print("  - Check camera video encoding settings (should be H.264)")
        
    elif not results['software_decode']:
        print("\n❌ PROBLEM: Software decoder cannot decode stream")
        print("\nPossible causes:")
        print("  1. Invalid H.264 stream")
        print("  2. Camera streaming issues")
        print("\nFix:")
        print("  - Restart camera")
        print("  - Check camera video settings")
        
    else:
        print("\n✅ STREAM IS WORKING!")
        print("\nThe RTSP stream is accessible and decodable.")
        print("If hardware decoder tests still fail, it's likely:")
        print("  1. H.264 profile incompatibility (camera using High Profile)")
        print("  2. nvv4l2decoder plugin issue")
        print("  3. Need to use software decode fallback")
        print("\nYour application will work with software decode.")
        print("Hardware decode is an optimization, not a requirement.")
    
    print()

if __name__ == "__main__":
    main()
