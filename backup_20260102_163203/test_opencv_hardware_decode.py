#!/usr/bin/env python3
"""
Test hardware decoder by running your actual application's method
This will show NVDEC activity in jtop
"""

import cv2
import sys
import time
import os

def test_opencv_with_gstreamer(rtsp_url, duration=30):
    """
    Test OpenCV with GStreamer hardware decoder backend
    This is what your application actually uses
    """
    
    print("="*70)
    print("Testing OpenCV with GStreamer Hardware Decoder")
    print("="*70)
    print(f"\nRTSP URL: {rtsp_url}")
    print(f"Duration: {duration} seconds\n")
    
    print("⚠️  IMPORTANT:")
    print("1. Open another terminal and run: jtop")
    print("2. Watch the NVDEC section")
    print("3. If you built OpenCV with CUDA + GStreamer, NVDEC should show activity\n")
    
    input("Press Enter when jtop is ready...")
    
    print(f"\nOpening stream with OpenCV (using GStreamer backend)...")
    
    # Method 1: Use GStreamer pipeline through OpenCV (hardware decode)
    gst_pipeline = (
        f"rtspsrc location={rtsp_url} latency=200 ! "
        "rtph264depay ! h264parse ! "
        "nvv4l2decoder ! "  # Hardware decoder
        "nvvidconv ! "
        "video/x-raw,format=BGRx ! "
        "videoconvert ! "
        "video/x-raw,format=BGR ! "
        "appsink drop=1"
    )
    
    print(f"Using GStreamer pipeline through OpenCV...")
    print(f"Pipeline: {gst_pipeline[:80]}...")
    
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    
    if not cap.isOpened():
        print("\n✗ Failed to open with GStreamer hardware decoder")
        print("Trying fallback to direct OpenCV...")
        
        # Fallback: Direct OpenCV (might use software decode)
        cap = cv2.VideoCapture(rtsp_url)
        
        if not cap.isOpened():
            print("✗ Failed to open stream entirely")
            return False
        else:
            print("✓ Opened with direct OpenCV (likely software decode)")
            print("  Note: NVDEC won't show activity - this is CPU decoding")
    else:
        print("✓ Opened with GStreamer pipeline!")
        print("  If NVDEC shows activity in jtop = Hardware decode working! ✅")
    
    print(f"\nReading frames for {duration} seconds...")
    print("Watch NVDEC in jtop NOW!\n")
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            ret, frame = cap.read()
            
            if not ret:
                print("\n✗ Failed to read frame")
                break
            
            frame_count += 1
            
            if frame_count == 1:
                print(f"✓ First frame received! Shape: {frame.shape}")
            
            # Progress indicator
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            if frame_count % 30 == 0:  # Update every 30 frames
                print(f"\rFrames: {frame_count} | Time: {elapsed}s / {duration}s | Remaining: {remaining}s", end='', flush=True)
            
            time.sleep(0.01)  # Small delay
        
        print(f"\n\n✓ Successfully read {frame_count} frames in {duration} seconds")
        print(f"  Average FPS: {frame_count/duration:.1f}")
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        cap.release()
    
    print("\n" + "="*70)
    print("Did you see NVDEC activity in jtop?")
    print("="*70)
    print("  YES → Hardware decoder is working! ✅")
    print("  NO  → Using software decoder (still works, just slower)")
    print("="*70 + "\n")
    
    return True

def check_opencv_gstreamer():
    """Check if OpenCV is built with GStreamer support"""
    print("="*70)
    print("Checking OpenCV Configuration")
    print("="*70)
    
    build_info = cv2.getBuildInformation()
    
    # Check GStreamer
    gstreamer = False
    for line in build_info.split('\n'):
        if 'GStreamer:' in line:
            print(f"  {line.strip()}")
            if 'YES' in line:
                gstreamer = True
                print("  ✓ GStreamer support is ENABLED")
            else:
                print("  ✗ GStreamer support is DISABLED")
            break
    
    # Check CUDA
    try:
        cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
        print(f"\n  CUDA devices: {cuda_count}")
        if cuda_count > 0:
            print("  ✓ CUDA is ENABLED")
        else:
            print("  ✗ CUDA not available")
    except:
        print("  ✗ CUDA not available")
    
    print()
    
    return gstreamer

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_opencv_hardware_decode.py '<RTSP_URL>' [duration]")
        print("\nExample:")
        print("  python test_opencv_hardware_decode.py 'rtsp://admin:pass@ip:554/path?channel=1&subtype=0' 30")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     Test Hardware Decoder (OpenCV + GStreamer Method)           ║
╚══════════════════════════════════════════════════════════════════╝

This tests the ACTUAL method your application uses.
""")
    
    # Check OpenCV build
    has_gstreamer = check_opencv_gstreamer()
    
    if not has_gstreamer:
        print("⚠️  WARNING: OpenCV was not built with GStreamer support!")
        print("   Hardware decode through GStreamer won't work.")
        print("   Rebuild OpenCV with GStreamer enabled.\n")
    
    # Run the test
    success = test_opencv_with_gstreamer(rtsp_url, duration)
    
    if success:
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        if has_gstreamer:
            print("\n✅ Your OpenCV has GStreamer support")
            print("✅ Stream opened successfully")
            print("\nIf you saw NVDEC activity:")
            print("  → Hardware decoder IS working in your application!")
            print("\nIf you did NOT see NVDEC:")
            print("  → Check if nvv4l2decoder plugin exists:")
            print("     gst-inspect-1.0 nvv4l2decoder")
            print("  → Your app will fallback to software decode automatically")
        else:
            print("\n⚠️  OpenCV doesn't have GStreamer support")
            print("   Your application uses software decode")
            print("   To enable hardware decode: rebuild OpenCV with GStreamer")
        
        print()

if __name__ == "__main__":
    main()
