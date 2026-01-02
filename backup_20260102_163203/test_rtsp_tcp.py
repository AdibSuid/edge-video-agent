#!/usr/bin/env python3
"""
Test RTSP with TCP transport (more reliable than UDP)
"""

import subprocess
import sys

def test_with_tcp(rtsp_url):
    """Test RTSP with TCP protocol"""
    print("="*70)
    print("Testing RTSP with TCP Transport")
    print("="*70)
    print(f"URL: {rtsp_url}\n")
    
    # Test 1: Basic connection with TCP
    print("1. Basic TCP connection test...")
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 
        'protocols=tcp',  # Force TCP
        'latency=200', 
        'num-buffers=30', '!',
        'fakesink'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ TCP connection works!\n")
            return True
        else:
            print("✗ TCP connection failed")
            if result.stderr:
                for line in result.stderr.split('\n')[:10]:
                    if line.strip():
                        print(f"  {line.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Timeout\n")
        return False

def test_software_decode_tcp(rtsp_url):
    """Test software decode with TCP"""
    print("\n2. Software decode with TCP...")
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}',
        'protocols=tcp',  # Force TCP
        'latency=200',
        'num-buffers=50', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'avdec_h264', '!',
        'fakesink', 'sync=false'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print("✓ Software decode works with TCP!\n")
            return True
        else:
            print("✗ Software decode failed")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Timeout\n")
        return False

def test_hardware_decode_tcp(rtsp_url):
    """Test hardware decode with TCP"""
    print("\n3. Hardware decode with TCP...")
    
    configs = [
        ("nvv4l2decoder - basic", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'protocols=tcp', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!', 'h264parse', '!',
            'nvv4l2decoder', '!',
            'fakesink', 'sync=false'
        ]),
        ("nvv4l2decoder + nvvidconv", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'protocols=tcp', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!', 'h264parse', '!',
            'nvv4l2decoder', '!',
            'nvvidconv', '!',
            'video/x-raw,format=BGRx', '!',
            'fakesink', 'sync=false'
        ]),
        ("omxh264dec (older Jetson)", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'protocols=tcp', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!', 'h264parse', '!',
            'omxh264dec', '!',
            'nvvidconv', '!',
            'fakesink', 'sync=false'
        ])
    ]
    
    working = []
    
    for name, cmd in configs:
        print(f"\n   Testing: {name}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"   ✓ {name} WORKS!")
                working.append(name)
            else:
                print(f"   ✗ Failed")
        except subprocess.TimeoutExpired:
            print(f"   ✗ Timeout")
    
    return working

def test_ffmpeg_tcp(rtsp_url):
    """Test with ffmpeg using TCP"""
    print("\n4. Testing with FFmpeg (TCP)...")
    
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',  # Force TCP
        '-i', rtsp_url,
        '-frames:v', '10',
        '-f', 'null',
        '-'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 or 'frame=' in result.stderr:
            print("✓ FFmpeg can read stream with TCP\n")
            return True
        else:
            print("✗ FFmpeg failed")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Timeout")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_rtsp_tcp.py '<RTSP_URL>'")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           RTSP with TCP Transport Test                          ║
╚══════════════════════════════════════════════════════════════════╝

Many cameras require TCP instead of UDP for RTSP.
VLC uses TCP by default, which is why it works.

""")
    
    # Run tests
    tcp_works = test_with_tcp(rtsp_url)
    
    if not tcp_works:
        print("\n" + "="*70)
        print("❌ Cannot connect even with TCP")
        print("="*70)
        print("\nTry:")
        print("1. Test URL in browser: http://192.168.0.130")
        print("2. Check camera RTSP settings")
        print("3. Try different RTSP path (check camera manual)")
        sys.exit(1)
    
    sw_works = test_software_decode_tcp(rtsp_url)
    hw_decoders = test_hardware_decode_tcp(rtsp_url)
    ffmpeg_works = test_ffmpeg_tcp(rtsp_url)
    
    # Summary
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"TCP Connection:      {'✓ WORKS' if tcp_works else '✗ FAILED'}")
    print(f"Software Decode:     {'✓ WORKS' if sw_works else '✗ FAILED'}")
    print(f"Hardware Decoders:   {len(hw_decoders)} working")
    if hw_decoders:
        for decoder in hw_decoders:
            print(f"  ✓ {decoder}")
    print(f"FFmpeg:              {'✓ WORKS' if ffmpeg_works else '✗ FAILED'}")
    
    # Recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS FOR YOUR CODE")
    print("="*70)
    
    if hw_decoders:
        print("\n✅ Hardware decoder works with TCP!")
        print("\nUse this GStreamer pipeline:")
        print("```")
        print(f"rtspsrc location={rtsp_url} protocols=tcp latency=200 ! \\")
        print("  rtph264depay ! h264parse ! \\")
        print("  nvv4l2decoder ! \\")
        print("  nvvidconv ! video/x-raw,format=BGRx ! \\")
        print("  appsink")
        print("```")
        
    elif sw_works:
        print("\n⚠ Only software decode works")
        print("\nUse this GStreamer pipeline:")
        print("```")
        print(f"rtspsrc location={rtsp_url} protocols=tcp latency=200 ! \\")
        print("  rtph264depay ! h264parse ! \\")
        print("  avdec_h264 ! \\")
        print("  videoconvert ! \\")
        print("  appsink")
        print("```")
        
    if ffmpeg_works:
        print("\n✅ FFmpeg works!")
        print("\nAlternative: Use FFmpeg in your Python code:")
        print("```python")
        print("cmd = [")
        print("    'ffmpeg',")
        print("    '-rtsp_transport', 'tcp',  # KEY: Use TCP!")
        print(f"    '-i', '{rtsp_url}',")
        print("    '-f', 'rawvideo',")
        print("    '-pix_fmt', 'bgr24',")
        print("    'pipe:1'")
        print("]")
        print("```")
    
    print("\n" + "="*70)
    print("KEY FINDING: Your camera requires TCP transport!")
    print("Add 'protocols=tcp' to rtspsrc or '-rtsp_transport tcp' to ffmpeg")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
