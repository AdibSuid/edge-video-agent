#!/usr/bin/env python3
"""
Test script for video encoding/decoding with CUDA and GStreamer enabled OpenCV
Tests various pipelines to verify hardware acceleration is working properly
"""

import cv2
import numpy as np
import time
import subprocess
import os
import sys

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def check_opencv_build():
    """Verify OpenCV is built with CUDA and GStreamer"""
    print_section("1. OpenCV Build Verification")
    
    print(f"OpenCV version: {cv2.__version__}")
    print(f"OpenCV location: {cv2.__file__}")
    
    build_info = cv2.getBuildInformation()
    
    # Check GStreamer
    gstreamer_enabled = False
    for line in build_info.split('\n'):
        if 'GStreamer:' in line:
            print(f"\nGStreamer: {line.strip()}")
            if 'YES' in line:
                gstreamer_enabled = True
                print("  ✓ GStreamer is ENABLED")
            else:
                print("  ✗ GStreamer is DISABLED")
            break
    
    # Check CUDA
    try:
        cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
        print(f"\nCUDA Devices: {cuda_count}")
        if cuda_count > 0:
            print("  ✓ CUDA is ENABLED")
            cuda_enabled = True
        else:
            print("  ✗ No CUDA devices found")
            cuda_enabled = False
    except Exception as e:
        print(f"  ✗ CUDA error: {e}")
        cuda_enabled = False
    
    return gstreamer_enabled, cuda_enabled

def test_gstreamer_read():
    """Test 1: Read video using GStreamer videotestsrc"""
    print_section("2. GStreamer Video Reading (videotestsrc)")
    
    try:
        # GStreamer pipeline to generate test video
        pipeline = "videotestsrc num-buffers=100 ! video/x-raw,width=1280,height=720,framerate=30/1 ! videoconvert ! appsink"
        
        print(f"Pipeline: {pipeline}")
        print("Opening video capture...")
        
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
        if not cap.isOpened():
            print("  ✗ Failed to open GStreamer pipeline")
            return False
        
        print("  ✓ Pipeline opened successfully")
        
        frame_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            
            if frame_count == 1:
                print(f"  ✓ First frame read: shape={frame.shape}, dtype={frame.dtype}")
        
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        cap.release()
        
        print(f"  ✓ Read {frame_count} frames in {elapsed:.2f}s ({fps:.1f} FPS)")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gstreamer_write():
    """Test 2: Write video using GStreamer appsrc"""
    print_section("3. GStreamer Video Writing (appsrc)")
    
    try:
        output_file = "/tmp/test_gst_write.mp4"
        width, height = 1280, 720
        fps = 30
        num_frames = 100
        
        # GStreamer pipeline for writing
        pipeline = (
            f"appsrc ! "
            f"video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 ! "
            f"videoconvert ! "
            f"x264enc speed-preset=ultrafast tune=zerolatency ! "
            f"qtmux ! "
            f"filesink location={output_file}"
        )
        
        print(f"Pipeline: {pipeline}")
        print(f"Output file: {output_file}")
        
        out = cv2.VideoWriter(pipeline, cv2.CAP_GSTREAMER, 0, fps, (width, height), True)
        
        if not out.isOpened():
            print("  ✗ Failed to open GStreamer writer")
            return False
        
        print("  ✓ Writer opened successfully")
        print(f"  Writing {num_frames} frames...")
        
        start_time = time.time()
        
        for i in range(num_frames):
            # Generate colorful test frame
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            color = int(255 * (i / num_frames))
            frame[:, :] = [color, 255 - color, 128]
            
            # Add text
            cv2.putText(frame, f"Frame {i}", (50, 100), 
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
            
            out.write(frame)
        
        elapsed = time.time() - start_time
        out.release()
        
        # Check if file was created
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / 1024  # KB
            print(f"  ✓ Video written successfully in {elapsed:.2f}s")
            print(f"  ✓ File size: {file_size:.1f} KB")
            print(f"  ✓ Average write speed: {num_frames/elapsed:.1f} FPS")
            return True
        else:
            print("  ✗ Output file was not created")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hardware_encode_gstreamer():
    """Test 3: Hardware encoding with GStreamer (nvv4l2h264enc)"""
    print_section("4. Hardware Encoding (nvv4l2h264enc)")
    
    try:
        output_file = "/tmp/test_hw_encode.mp4"
        
        # GStreamer pipeline with hardware encoder
        cmd = [
            'gst-launch-1.0', '-e',
            'videotestsrc', 'num-buffers=250', '!',
            'video/x-raw,width=1920,height=1080,framerate=30/1', '!',
            'nvvidconv', '!',
            'video/x-raw(memory:NVMM),format=I420', '!',
            'nvv4l2h264enc', 'bitrate=4000000', '!',
            'h264parse', '!',
            'qtmux', '!',
            'filesink', f'location={output_file}'
        ]
        
        print("Command:", ' '.join(cmd))
        print("Encoding 250 frames at 1920x1080...")
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        elapsed = time.time() - start_time
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / 1024  # KB
            fps = 250 / elapsed
            print(f"  ✓ Hardware encoding successful!")
            print(f"  ✓ Time: {elapsed:.2f}s ({fps:.1f} FPS)")
            print(f"  ✓ File size: {file_size:.1f} KB")
            print(f"  ✓ Output: {output_file}")
            return True, elapsed
        else:
            print(f"  ✗ Hardware encoding failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False, 0
            
    except subprocess.TimeoutExpired:
        print("  ✗ Timeout (30s exceeded)")
        return False, 0
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, 0

def test_software_encode_gstreamer():
    """Test 4: Software encoding with GStreamer (x264enc)"""
    print_section("5. Software Encoding (x264enc)")
    
    try:
        output_file = "/tmp/test_sw_encode.mp4"
        
        # GStreamer pipeline with software encoder
        cmd = [
            'gst-launch-1.0', '-e',
            'videotestsrc', 'num-buffers=250', '!',
            'video/x-raw,width=1920,height=1080,framerate=30/1', '!',
            'videoconvert', '!',
            'x264enc', 'speed-preset=ultrafast', 'bitrate=4000', '!',
            'h264parse', '!',
            'qtmux', '!',
            'filesink', f'location={output_file}'
        ]
        
        print("Command:", ' '.join(cmd))
        print("Encoding 250 frames at 1920x1080...")
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        elapsed = time.time() - start_time
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file) / 1024  # KB
            fps = 250 / elapsed
            print(f"  ✓ Software encoding successful!")
            print(f"  ✓ Time: {elapsed:.2f}s ({fps:.1f} FPS)")
            print(f"  ✓ File size: {file_size:.1f} KB")
            print(f"  ✓ Output: {output_file}")
            return True, elapsed
        else:
            print(f"  ✗ Software encoding failed")
            if result.stderr:
                print(f"  Error: {result.stderr[:300]}")
            return False, 0
            
    except subprocess.TimeoutExpired:
        print("  ✗ Timeout (60s exceeded)")
        return False, 0
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, 0

def test_opencv_cuda_operations():
    """Test 5: CUDA operations with OpenCV"""
    print_section("6. OpenCV CUDA Operations")
    
    try:
        # Check if CUDA is available
        cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
        if cuda_count == 0:
            print("  ✗ No CUDA devices available")
            return False
        
        print(f"  ✓ CUDA devices: {cuda_count}")
        
        # Create test image
        img = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        print(f"  Test image shape: {img.shape}")
        
        # Upload to GPU
        print("\n  Testing GPU upload...")
        start = time.time()
        gpu_img = cv2.cuda_GpuMat()
        gpu_img.upload(img)
        upload_time = (time.time() - start) * 1000
        print(f"  ✓ GPU upload: {upload_time:.2f}ms")
        
        # Test Gaussian blur on GPU
        print("\n  Testing CUDA Gaussian blur...")
        start = time.time()
        gaussian_filter = cv2.cuda.createGaussianFilter(
            cv2.CV_8UC3, cv2.CV_8UC3, (15, 15), 3
        )
        gpu_blurred = gaussian_filter.apply(gpu_img)
        blur_time = (time.time() - start) * 1000
        print(f"  ✓ CUDA blur: {blur_time:.2f}ms")
        
        # Download from GPU
        print("\n  Testing GPU download...")
        start = time.time()
        result = gpu_blurred.download()
        download_time = (time.time() - start) * 1000
        print(f"  ✓ GPU download: {download_time:.2f}ms")
        
        # Compare with CPU version
        print("\n  Comparing with CPU version...")
        start = time.time()
        cpu_blurred = cv2.GaussianBlur(img, (15, 15), 3)
        cpu_time = (time.time() - start) * 1000
        print(f"  ✓ CPU blur: {cpu_time:.2f}ms")
        
        speedup = cpu_time / blur_time if blur_time > 0 else 0
        print(f"\n  ⚡ CUDA speedup: {speedup:.2f}x")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_decode():
    """Test 6: Decode a video file"""
    print_section("7. Video Decoding Test")
    
    # Use one of the encoded files
    test_files = [
        "/tmp/test_hw_encode.mp4",
        "/tmp/test_sw_encode.mp4",
        "/tmp/test_gst_write.mp4"
    ]
    
    test_file = None
    for f in test_files:
        if os.path.exists(f):
            test_file = f
            break
    
    if not test_file:
        print("  ⚠ No test video files found. Skipping decode test.")
        return False
    
    print(f"Test file: {test_file}")
    
    try:
        # Test with OpenCV
        print("\n  Testing OpenCV decode...")
        cap = cv2.VideoCapture(test_file)
        
        if not cap.isOpened():
            print("  ✗ Failed to open video file")
            return False
        
        frame_count = 0
        start_time = time.time()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
        
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        
        cap.release()
        
        print(f"  ✓ Decoded {frame_count} frames in {elapsed:.2f}s")
        print(f"  ✓ Decode speed: {fps:.1f} FPS")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     OpenCV CUDA + GStreamer Video Encode/Decode Test Suite      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # Run all tests
    results = {}
    
    # 1. Verify build
    gst_enabled, cuda_enabled = check_opencv_build()
    results['OpenCV Build'] = gst_enabled and cuda_enabled
    
    if not gst_enabled:
        print("\n⚠ WARNING: GStreamer is not enabled in OpenCV build!")
        print("   Some tests will fail. Please rebuild OpenCV with GStreamer support.")
    
    if not cuda_enabled:
        print("\n⚠ WARNING: CUDA is not enabled in OpenCV build!")
        print("   GPU acceleration tests will fail. Please rebuild OpenCV with CUDA support.")
    
    # 2. GStreamer read test
    results['GStreamer Read'] = test_gstreamer_read()
    
    # 3. GStreamer write test
    results['GStreamer Write'] = test_gstreamer_write()
    
    # 4. Hardware encoding
    hw_success, hw_time = test_hardware_encode_gstreamer()
    results['Hardware Encode'] = hw_success
    
    # 5. Software encoding
    sw_success, sw_time = test_software_encode_gstreamer()
    results['Software Encode'] = sw_success
    
    # 6. CUDA operations
    if cuda_enabled:
        results['CUDA Operations'] = test_opencv_cuda_operations()
    else:
        results['CUDA Operations'] = False
    
    # 7. Video decoding
    results['Video Decode'] = test_video_decode()
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name:25s}: {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    # Performance comparison
    if hw_success and sw_success and hw_time > 0 and sw_time > 0:
        print_section("PERFORMANCE COMPARISON")
        speedup = sw_time / hw_time
        print(f"  Hardware encoding: {hw_time:.2f}s")
        print(f"  Software encoding: {sw_time:.2f}s")
        print(f"  ⚡ Hardware speedup: {speedup:.2f}x")
    
    # Recommendations
    print_section("RECOMMENDATIONS")
    
    if results['Hardware Encode']:
        print("  ✓ Hardware encoding is working!")
        print("    Use: nvv4l2h264enc in GStreamer pipelines")
    else:
        print("  ✗ Hardware encoding failed.")
        print("    Check: GStreamer NVIDIA plugins installation")
        print("    Run: gst-inspect-1.0 nvv4l2h264enc")
    
    if results['CUDA Operations']:
        print("\n  ✓ CUDA operations are working!")
        print("    Your OpenCV can use GPU acceleration")
    else:
        print("\n  ✗ CUDA operations failed.")
        print("    Rebuild OpenCV with CUDA support")
    
    if results['GStreamer Read'] and results['GStreamer Write']:
        print("\n  ✓ GStreamer integration is working!")
        print("    You can use GStreamer pipelines in OpenCV")
    else:
        print("\n  ✗ GStreamer integration failed.")
        print("    Rebuild OpenCV with GStreamer support")
    
    print("\n" + "="*70)
    print("Test files location: /tmp/test_*.mp4")
    print("You can play them with: ffplay /tmp/test_hw_encode.mp4")
    print("="*70 + "\n")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
