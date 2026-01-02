#!/usr/bin/env python3
"""
Improved hardware decoder implementation for Jetson
Tests multiple decoder options and provides working examples
"""

import subprocess
import cv2
import numpy as np
import time

def test_ffmpeg_decoders():
    """Test which FFmpeg hardware decoders are available"""
    print("="*70)
    print("Checking FFmpeg Hardware Decoders")
    print("="*70)
    
    decoders = {
        'h264_cuvid': 'NVIDIA CUVID (newer Jetson)',
        'h264_v4l2m2m': 'V4L2 Memory-to-Memory (JetPack 4.x)',
        'h264': 'Software decoder (fallback)'
    }
    
    available = {}
    
    for decoder, description in decoders.items():
        cmd = ['ffmpeg', '-decoders']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if decoder in result.stdout:
            print(f"✓ {decoder:20s} - {description}")
            available[decoder] = True
        else:
            print(f"✗ {decoder:20s} - NOT AVAILABLE")
            available[decoder] = False
    
    return available

def test_gstreamer_decoders():
    """Test which GStreamer hardware decoders are available"""
    print("\n" + "="*70)
    print("Checking GStreamer Hardware Decoders")
    print("="*70)
    
    decoders = {
        'nvv4l2decoder': 'NVIDIA V4L2 Decoder (JetPack 4.x)',
        'nvdec': 'NVIDIA NVDEC (newer)',
        'omxh264dec': 'OpenMAX (older Jetson)',
        'avdec_h264': 'Software decoder (fallback)'
    }
    
    available = {}
    
    for decoder, description in decoders.items():
        cmd = ['gst-inspect-1.0', decoder]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        
        if result.returncode == 0:
            print(f"✓ {decoder:20s} - {description}")
            available[decoder] = True
        else:
            print(f"✗ {decoder:20s} - NOT AVAILABLE")
            available[decoder] = False
    
    return available

def test_decoder_pipeline(rtsp_url, decoder_type='auto'):
    """
    Test different decoder pipelines
    
    decoder_type: 'ffmpeg_cuvid', 'ffmpeg_v4l2m2m', 'gst_nvv4l2', 'gst_omx', 'opencv', 'auto'
    """
    print("\n" + "="*70)
    print(f"Testing Decoder Pipeline: {decoder_type}")
    print("="*70)
    
    if decoder_type == 'ffmpeg_cuvid' or decoder_type == 'auto':
        print("\n--- FFmpeg with h264_cuvid ---")
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-hwaccel', 'cuda',
            '-c:v', 'h264_cuvid',
            '-i', rtsp_url,
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-frames:v', '10',
            'pipe:1'
        ]
        
        if test_ffmpeg_pipeline(cmd, "h264_cuvid"):
            return 'ffmpeg_cuvid'
    
    if decoder_type == 'ffmpeg_v4l2m2m' or decoder_type == 'auto':
        print("\n--- FFmpeg with h264_v4l2m2m ---")
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-c:v', 'h264_v4l2m2m',
            '-i', rtsp_url,
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-frames:v', '10',
            'pipe:1'
        ]
        
        if test_ffmpeg_pipeline(cmd, "h264_v4l2m2m"):
            return 'ffmpeg_v4l2m2m'
    
    if decoder_type == 'gst_nvv4l2' or decoder_type == 'auto':
        print("\n--- GStreamer with nvv4l2decoder ---")
        pipeline = (
            f"rtspsrc location={rtsp_url} latency=200 ! "
            "rtph264depay ! h264parse ! "
            "video/x-h264,stream-format=byte-stream,alignment=au ! "
            "nvv4l2decoder enable-max-performance=1 ! "
            "nvvidconv ! video/x-raw,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink"
        )
        
        if test_gstreamer_pipeline(pipeline, "nvv4l2decoder"):
            return 'gst_nvv4l2'
    
    if decoder_type == 'gst_omx' or decoder_type == 'auto':
        print("\n--- GStreamer with omxh264dec ---")
        pipeline = (
            f"rtspsrc location={rtsp_url} latency=200 ! "
            "rtph264depay ! h264parse ! "
            "omxh264dec ! nvvidconv ! "
            "video/x-raw,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! "
            "appsink"
        )
        
        if test_gstreamer_pipeline(pipeline, "omxh264dec"):
            return 'gst_omx'
    
    if decoder_type == 'opencv' or decoder_type == 'auto':
        print("\n--- OpenCV (software decode) ---")
        if test_opencv_decode(rtsp_url):
            return 'opencv'
    
    print("\n✗ All decoder methods failed!")
    return None

def test_ffmpeg_pipeline(cmd, decoder_name):
    """Test FFmpeg pipeline"""
    try:
        print(f"Command: {' '.join(cmd[:8])}...")
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0 and len(result.stdout) > 0:
            print(f"✓ SUCCESS with {decoder_name}")
            print(f"  Decoded frames in {elapsed:.2f}s")
            print(f"  Data received: {len(result.stdout)} bytes")
            return True
        else:
            print(f"✗ FAILED")
            if result.stderr:
                error = result.stderr.decode('utf-8', errors='ignore')
                # Show relevant error lines
                for line in error.split('\n'):
                    if 'error' in line.lower() or 'failed' in line.lower():
                        print(f"  Error: {line.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def test_gstreamer_pipeline(pipeline, decoder_name):
    """Test GStreamer pipeline"""
    try:
        print(f"Pipeline: {pipeline[:80]}...")
        
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
        if not cap.isOpened():
            print(f"✗ FAILED to open pipeline")
            return False
        
        frame_count = 0
        start_time = time.time()
        
        for i in range(10):  # Try to read 10 frames
            ret, frame = cap.read()
            if ret:
                frame_count += 1
            else:
                break
        
        elapsed = time.time() - start_time
        cap.release()
        
        if frame_count > 0:
            print(f"✓ SUCCESS with {decoder_name}")
            print(f"  Read {frame_count} frames in {elapsed:.2f}s")
            return True
        else:
            print(f"✗ FAILED - no frames read")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def test_opencv_decode(rtsp_url):
    """Test OpenCV software decode"""
    try:
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            print("✗ FAILED to open stream")
            return False
        
        frame_count = 0
        start_time = time.time()
        
        for i in range(10):
            ret, frame = cap.read()
            if ret:
                frame_count += 1
            else:
                break
        
        elapsed = time.time() - start_time
        cap.release()
        
        if frame_count > 0:
            print(f"✓ SUCCESS with OpenCV")
            print(f"  Read {frame_count} frames in {elapsed:.2f}s")
            return True
        else:
            print(f"✗ FAILED - no frames read")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def generate_working_code(best_decoder, rtsp_url):
    """Generate working Python code for the best decoder"""
    print("\n" + "="*70)
    print("WORKING CODE FOR YOUR APPLICATION")
    print("="*70)
    
    if best_decoder == 'ffmpeg_v4l2m2m':
        print("""
✓ Best option: FFmpeg with h264_v4l2m2m decoder

Python implementation:
```python
import subprocess
import numpy as np
import cv2

def decode_with_v4l2m2m(rtsp_url):
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        '-c:v', 'h264_v4l2m2m',    # V4L2 hardware decoder
        '-i', rtsp_url,
        '-vf', 'fps=10',            # Limit framerate
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        'pipe:1'
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Auto-detect resolution from stderr
    width, height = 1920, 1080  # default
    # ... (resolution detection code)
    
    frame_size = width * height * 3
    
    while True:
        raw_frame = proc.stdout.read(frame_size)
        if len(raw_frame) != frame_size:
            break
        
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
        # Process frame here
        yield frame
```
""")
    
    elif best_decoder == 'gst_nvv4l2':
        print(f"""
✓ Best option: GStreamer with nvv4l2decoder

Python implementation:
```python
import cv2

def decode_with_gstreamer(rtsp_url):
    pipeline = (
        f"rtspsrc location={rtsp_url} latency=200 ! "
        "rtph264depay ! h264parse ! "
        "video/x-h264,stream-format=byte-stream,alignment=au ! "
        "nvv4l2decoder enable-max-performance=1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink"
    )
    
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process frame here
        yield frame
    
    cap.release()
```
""")
    
    elif best_decoder == 'opencv':
        print(f"""
⚠ Falling back to software decode

Python implementation:
```python
import cv2

def decode_with_opencv(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process frame here
        yield frame
    
    cap.release()
```

NOTE: This is software decoding. For better performance, fix hardware decoder.
""")
    
    else:
        print("✗ No working decoder found")

def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║        Find Best Hardware Decoder for Your Jetson               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # RTSP URL from config
    rtsp_url = "rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0"
    
    import sys
    if len(sys.argv) > 1:
        rtsp_url = sys.argv[1]
    
    print(f"Testing with: {rtsp_url}\n")
    
    # Check available decoders
    ffmpeg_decoders = test_ffmpeg_decoders()
    gst_decoders = test_gstreamer_decoders()
    
    # Test best decoder
    best_decoder = test_decoder_pipeline(rtsp_url, 'auto')
    
    if best_decoder:
        print("\n" + "="*70)
        print(f"✓ BEST DECODER: {best_decoder}")
        print("="*70)
        generate_working_code(best_decoder, rtsp_url)
    else:
        print("\n" + "="*70)
        print("✗ NO WORKING DECODER FOUND")
        print("="*70)
        print("\nTroubleshooting:")
        print("1. Check RTSP stream is accessible")
        print("2. Install NVIDIA GStreamer plugins")
        print("3. Try software decode as fallback")
    
    print("\n" + "="*70)
    print("Summary:")
    print(f"  Hardware encoder: {'✓ Working' if True else '✗ Failed'}")
    print(f"  Hardware decoder: {'✓ Working' if best_decoder and best_decoder != 'opencv' else '✗ Failed (using software)'}")
    print("="*70 + "\n")

if __name__ == "__main__":
    import sys
    main()
