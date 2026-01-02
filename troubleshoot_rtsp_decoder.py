#!/usr/bin/env python3
"""
Quick RTSP Hardware Decoder Troubleshooter
Tests different decoder configurations to find what works
"""

import subprocess
import sys

def test_pipeline(cmd, name, timeout=15):
    """Test a GStreamer pipeline"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print("Running...")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            print(f"✓ SUCCESS - {name} works!")
            return True
        else:
            print(f"✗ FAILED - Return code: {result.returncode}")
            # Show relevant error lines
            if result.stderr:
                print("\nError details:")
                for line in result.stderr.split('\n'):
                    if any(word in line.lower() for word in ['error', 'failed', 'could not', 'unable']):
                        print(f"  {line.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT after {timeout}s")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python troubleshoot_rtsp_decoder.py <RTSP_URL>")
        print("\nExample:")
        print("  python troubleshoot_rtsp_decoder.py rtsp://admin:pass@192.168.0.130:554/stream")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          RTSP Hardware Decoder Troubleshooter                   ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    print(f"RTSP URL: {rtsp_url}")
    print("Testing 100 frames (~3-4 seconds of video)")
    
    results = {}
    
    # Test 1: Software decoder (baseline)
    print("\n" + "="*70)
    print("BASELINE: Software Decoder")
    print("="*70)
    
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'avdec_h264', '!',
        'fakesink', 'sync=false'
    ]
    
    results['software'] = test_pipeline(cmd, "Software Decoder (avdec_h264)")
    
    # Test 2: Basic hardware decoder
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'nvvidconv', '!',
        'fakesink', 'sync=false'
    ]
    
    results['hw_basic'] = test_pipeline(cmd, "Hardware Decoder - Basic (nvv4l2decoder)")
    
    # Test 3: Hardware decoder with explicit caps
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'video/x-h264,stream-format=byte-stream,alignment=au', '!',
        'nvv4l2decoder', 'enable-max-performance=1', '!',
        'nvvidconv', '!',
        'fakesink', 'sync=false'
    ]
    
    results['hw_explicit'] = test_pipeline(cmd, "Hardware Decoder - Explicit Caps")
    
    # Test 4: Hardware decoder without nvvidconv
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'fakesink', 'sync=false'
    ]
    
    results['hw_no_conv'] = test_pipeline(cmd, "Hardware Decoder - Without nvvidconv")
    
    # Test 5: Hardware decoder with different properties
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', 'enable-max-performance=1', 'drop-frame-interval=0', '!',
        'nvvidconv', '!',
        'fakesink', 'sync=false'
    ]
    
    results['hw_tuned'] = test_pipeline(cmd, "Hardware Decoder - Tuned Properties")
    
    # Test 6: OMX decoder (for older Jetson)
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=100', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'omxh264dec', '!',
        'nvvidconv', '!',
        'fakesink', 'sync=false'
    ]
    
    results['omx'] = test_pipeline(cmd, "OMX Decoder (omxh264dec)")
    
    # Test 7: TCP instead of UDP
    rtsp_tcp = rtsp_url.replace('rtsp://', 'rtspt://')
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_tcp}', 'latency=200', 'num-buffers=100', 'protocols=tcp', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'nvvidconv', '!',
        'fakesink', 'sync=false'
    ]
    
    results['hw_tcp'] = test_pipeline(cmd, "Hardware Decoder - Force TCP")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for test_name, success in results.items():
        status = "✓ WORKS" if success else "✗ FAILED"
        print(f"  {test_name:25s}: {status}")
    
    # Recommendations
    print("\n" + "="*70)
    print("ANALYSIS & RECOMMENDATIONS")
    print("="*70)
    
    if not results['software']:
        print("\n❌ CRITICAL: Even software decoder failed!")
        print("   Problem: RTSP stream is not accessible or invalid")
        print("   Fixes:")
        print("   1. Check network connectivity to camera")
        print("   2. Verify RTSP URL and credentials")
        print("   3. Try accessing stream with VLC or ffplay first:")
        print(f"      ffplay {rtsp_url}")
    
    elif any([results['hw_basic'], results['hw_explicit'], results['hw_tuned']]):
        print("\n✅ GOOD NEWS: Hardware decoder works with RTSP!")
        
        if results['hw_basic']:
            print("\n✓ Best option: Basic nvv4l2decoder")
            print("\n  Working pipeline:")
            print("  ```")
            print(f"  rtspsrc location={rtsp_url} latency=200 ! \\")
            print("    rtph264depay ! h264parse ! \\")
            print("    nvv4l2decoder ! nvvidconv ! \\")
            print("    video/x-raw,format=BGRx ! appsink")
            print("  ```")
        
        elif results['hw_explicit']:
            print("\n✓ Best option: nvv4l2decoder with explicit caps")
            print("\n  Working pipeline:")
            print("  ```")
            print(f"  rtspsrc location={rtsp_url} latency=200 ! \\")
            print("    rtph264depay ! h264parse ! \\")
            print("    video/x-h264,stream-format=byte-stream,alignment=au ! \\")
            print("    nvv4l2decoder enable-max-performance=1 ! \\")
            print("    nvvidconv ! video/x-raw,format=BGRx ! appsink")
            print("  ```")
        
        elif results['hw_tuned']:
            print("\n✓ Best option: nvv4l2decoder with tuned properties")
            print("\n  Working pipeline:")
            print("  ```")
            print(f"  rtspsrc location={rtsp_url} latency=200 ! \\")
            print("    rtph264depay ! h264parse ! \\")
            print("    nvv4l2decoder enable-max-performance=1 drop-frame-interval=0 ! \\")
            print("    nvvidconv ! video/x-raw,format=BGRx ! appsink")
            print("  ```")
    
    elif results['omx']:
        print("\n✓ OMX decoder works!")
        print("   Your Jetson may be running older JetPack")
        print("\n  Working pipeline:")
        print("  ```")
        print(f"  rtspsrc location={rtsp_url} latency=200 ! \\")
        print("    rtph264depay ! h264parse ! \\")
        print("    omxh264dec ! nvvidconv ! \\")
        print("    video/x-raw,format=BGRx ! appsink")
        print("  ```")
    
    else:
        print("\n⚠ Hardware decoder doesn't work with RTSP")
        print("   But software decoder works, so you can still process video")
        print("\n  Possible reasons:")
        print("  1. Camera H.264 profile incompatible (High profile)")
        print("  2. Resolution too high (>1920x1080)")
        print("  3. Hardware decoder driver issues")
        print("\n  Workarounds:")
        print("  1. Use software decoder (automatic fallback)")
        print("  2. Change camera settings:")
        print("     - H.264 Profile: Baseline or Main (not High)")
        print("     - Resolution: 1920x1080 or lower")
        print("     - Bitrate: 4-8 Mbps")
        print("  3. Update JetPack/L4T to latest version")
    
    # Check camera stream info
    print("\n" + "="*70)
    print("CAMERA STREAM INFO")
    print("="*70)
    print("\nChecking stream details with ffprobe...")
    
    cmd = ['ffprobe', '-i', rtsp_url, '-show_streams', '-select_streams', 'v:0']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 or result.stderr:
            output = result.stdout + result.stderr
            print("\nRelevant stream information:")
            for line in output.split('\n'):
                if any(word in line.lower() for word in 
                       ['codec', 'profile', 'level', 'width', 'height', 'frame', 'bitrate']):
                    print(f"  {line.strip()}")
    except:
        print("  Could not retrieve stream info")
    
    print("\n" + "="*70)
    print("Next Steps:")
    print("1. Use the working pipeline in your application")
    print("2. If no hardware decoder works, app will auto-fallback to software")
    print("3. Consider camera settings if hardware decode fails")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
