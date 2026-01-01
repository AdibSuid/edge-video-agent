#!/usr/bin/env python3
"""
Performance comparison script for hardware vs software encoding/decoding
Run this to verify hardware acceleration is working properly
"""

import subprocess
import time
import cv2
import sys

def run_command(cmd, description, timeout=10):
    """Run a command and measure execution time"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd[:3])}...")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✓ SUCCESS - Completed in {elapsed:.2f} seconds")
            return True, elapsed
        else:
            print(f"✗ FAILED - Return code: {result.returncode}")
            print(f"Error: {result.stderr[:200]}")
            return False, 0
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT after {timeout} seconds")
        return False, 0
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False, 0

def test_hardware_decoder(rtsp_url):
    """Test NVIDIA hardware decoder"""
    cmd = [
        'gst-launch-1.0', '-e',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'nvvidconv', '!',
        'video/x-raw,format=BGRx', '!',
        'videoconvert', '!',
        'fakesink'
    ]
    return run_command(cmd, "NVIDIA Hardware Decoder (nvv4l2decoder)", timeout=5)

def test_software_decoder(rtsp_url):
    """Test software decoder with OpenCV"""
    print(f"\n{'='*60}")
    print(f"Testing: Software Decoder (OpenCV)")
    print(f"{'='*60}")
    
    try:
        start_time = time.time()
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            print("✗ FAILED - Could not open stream")
            return False, 0
        
        # Read 100 frames
        frames_read = 0
        for i in range(100):
            ret, frame = cap.read()
            if ret:
                frames_read += 1
            if i >= 100:
                break
        
        cap.release()
        elapsed = time.time() - start_time
        
        if frames_read > 50:
            print(f"✓ SUCCESS - Read {frames_read} frames in {elapsed:.2f} seconds")
            return True, elapsed
        else:
            print(f"✗ FAILED - Only read {frames_read} frames")
            return False, 0
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False, 0

def test_hardware_encoder():
    """Test NVIDIA hardware encoder"""
    cmd = [
        'gst-launch-1.0', '-e',
        'videotestsrc', 'num-buffers=250', '!',
        'video/x-raw,width=1280,height=720,framerate=25/1', '!',
        'nvvidconv', '!',
        'video/x-raw(memory:NVMM),format=I420', '!',
        'nvv4l2h264enc', 'bitrate=2000000', '!',
        'h264parse', '!',
        'qtmux', '!',
        'filesink', 'location=/tmp/hw_test.mp4'
    ]
    return run_command(cmd, "NVIDIA Hardware Encoder (nvv4l2h264enc)", timeout=15)

def test_software_encoder():
    """Test software encoder with ffmpeg"""
    cmd = [
        'gst-launch-1.0', '-e',
        'videotestsrc', 'num-buffers=250', '!',
        'video/x-raw,width=1280,height=720,framerate=25/1', '!',
        'videoconvert', '!',
        'x264enc', 'bitrate=2000', 'speed-preset=1', '!',  # speed-preset=1 = ultrafast
        'h264parse', '!',
        'qtmux', '!',
        'filesink', 'location=/tmp/sw_test.mp4'
    ]
    return run_command(cmd, "Software Encoder (x264enc)", timeout=15)

def check_gpu_usage():
    """Check current GPU encoder/decoder usage"""
    print(f"\n{'='*60}")
    print("Current GPU Usage")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(['sudo', 'tegrastats', '--interval', '1000', '--stop'],
                              capture_output=True, text=True, timeout=2)
        
        # Parse tegrastats output
        for line in result.stdout.split('\n'):
            if 'NVENC' in line or 'NVDEC' in line:
                print(line)
        
        # Also check nvmap allocations
        result = subprocess.run(['cat', '/sys/kernel/debug/nvmap/iovmm/allocations'],
                              capture_output=True, text=True)
        
        nvenc_count = result.stdout.count('nvenc')
        nvdec_count = result.stdout.count('nvdec')
        
        print(f"\nActive allocations:")
        print(f"  NVENC: {nvenc_count}")
        print(f"  NVDEC: {nvdec_count}")
        
    except Exception as e:
        print(f"Could not check GPU usage: {e}")

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║   NVIDIA Jetson Hardware Acceleration Performance Test    ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Get RTSP URL from user
    if len(sys.argv) > 1:
        rtsp_url = sys.argv[1]
    else:
        print("Enter RTSP URL for testing (or press Enter to skip decoder tests):")
        print("Example: rtsp://admin:password@192.168.0.130:554/stream")
        rtsp_url = input("> ").strip()
    
    results = {}
    
    # Test decoders if URL provided
    if rtsp_url:
        print("\n" + "="*60)
        print("DECODER PERFORMANCE COMPARISON")
        print("="*60)
        
        hw_success, hw_time = test_hardware_decoder(rtsp_url)
        results['hw_decoder'] = (hw_success, hw_time)
        
        sw_success, sw_time = test_software_decoder(rtsp_url)
        results['sw_decoder'] = (sw_success, sw_time)
        
        if hw_success and sw_success:
            speedup = sw_time / hw_time if hw_time > 0 else 0
            print(f"\n{'='*60}")
            print(f"DECODER SPEEDUP: {speedup:.2f}x")
            print(f"Hardware: {hw_time:.2f}s | Software: {sw_time:.2f}s")
            print(f"{'='*60}")
    
    # Test encoders
    print("\n" + "="*60)
    print("ENCODER PERFORMANCE COMPARISON")
    print("="*60)
    
    hw_success, hw_time = test_hardware_encoder()
    results['hw_encoder'] = (hw_success, hw_time)
    
    sw_success, sw_time = test_software_encoder()
    results['sw_encoder'] = (sw_success, sw_time)
    
    if hw_success and sw_success:
        speedup = sw_time / hw_time if hw_time > 0 else 0
        print(f"\n{'='*60}")
        print(f"ENCODER SPEEDUP: {speedup:.2f}x")
        print(f"Hardware: {hw_time:.2f}s | Software: {sw_time:.2f}s")
        print(f"{'='*60}")
    
    # Check GPU usage
    check_gpu_usage()
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for test_name, (success, elapsed) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        time_str = f"{elapsed:.2f}s" if success else "N/A"
        print(f"{test_name:20s}: {status:8s} ({time_str})")
    
    # Recommendations
    print(f"\n{'='*60}")
    print("RECOMMENDATIONS")
    print(f"{'='*60}")
    
    if results.get('hw_decoder', (False, 0))[0]:
        print("✓ Hardware decoder working - use in production")
    else:
        print("✗ Hardware decoder failed - check GStreamer NVIDIA plugins")
    
    if results.get('hw_encoder', (False, 0))[0]:
        print("✓ Hardware encoder working - use in production")
    else:
        print("✗ Hardware encoder failed - check GStreamer NVIDIA plugins")
    
    print("\nFor best performance:")
    print("1. Set Jetson to MAX mode: sudo nvpmodel -m 0")
    print("2. Enable max clocks: sudo jetson_clocks")
    print("3. Monitor with: sudo tegrastats")
    print("")

if __name__ == "__main__":
    main()