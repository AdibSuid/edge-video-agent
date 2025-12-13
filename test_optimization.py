#!/usr/bin/env python3
"""
Quick test to verify Jetson Orin optimization is working
"""

import sys
import time

def test_opencv_cuda():
    """Test OpenCV CUDA support"""
    print("=" * 60)
    print("1. Testing OpenCV CUDA Support")
    print("=" * 60)
    try:
        import cv2
        print(f"✓ OpenCV version: {cv2.__version__}")
        cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
        print(f"✓ CUDA devices: {cuda_count}")
        if cuda_count > 0:
            print("✓ CUDA is available!")
            return True
        else:
            print("✗ CUDA not available")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_cuda_motion_detector():
    """Test CUDA motion detector"""
    print("\n" + "=" * 60)
    print("2. Testing CUDA Motion Detector")
    print("=" * 60)
    try:
        from motion_detector_cuda import MotionDetectorCUDA
        import numpy as np
        
        detector = MotionDetectorCUDA()
        info = detector.get_info()
        
        print(f"✓ Detector initialized")
        print(f"  - Mode: {info['mode']}")
        print(f"  - CUDA Available: {info['cuda_available']}")
        print(f"  - CUDA Devices: {info['cuda_device_count']}")
        print(f"  - Detection Scale: {info['detection_scale']}")
        print(f"  - Frame Skip: {info['frame_skip']}")
        
        # Performance test
        print("\n  Running performance test (10 frames)...")
        frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        
        times = []
        for i in range(10):
            start = time.time()
            detector.detect(frame)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        print(f"  - Average detection time: {avg_time:.2f}ms")
        
        if info['cuda_available'] and avg_time < 10:
            print(f"✓ Performance: EXCELLENT (GPU accelerated)")
        elif avg_time < 20:
            print(f"✓ Performance: GOOD")
        else:
            print(f"⚠ Performance: Could be better (check CUDA)")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ffmpeg_hardware():
    """Test FFmpeg hardware encoding support"""
    print("\n" + "=" * 60)
    print("3. Testing FFmpeg Hardware Encoding")
    print("=" * 60)
    try:
        import subprocess
        
        # Check encoders
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        encoders = result.stdout
        has_v4l2m2m = 'h264_v4l2m2m' in encoders
        has_nvenc = 'h264_nvenc' in encoders
        
        print(f"  V4L2M2M (Jetson HW): {'✓ Available' if has_v4l2m2m else '✗ Not found'}")
        print(f"  NVENC: {'✓ Available' if has_nvenc else '✗ Not found'}")
        
        if has_v4l2m2m or has_nvenc:
            print("✓ Hardware encoding available")
            return True
        else:
            print("⚠ No hardware encoding found")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_platform_detection():
    """Test platform detection"""
    print("\n" + "=" * 60)
    print("4. Testing Platform Detection")
    print("=" * 60)
    try:
        import os
        
        is_jetson = os.path.exists('/etc/nv_tegra_release')
        print(f"  Jetson detected: {'✓ Yes' if is_jetson else '✗ No'}")
        
        if is_jetson:
            with open('/etc/nv_tegra_release', 'r') as f:
                content = f.read()
                print(f"  Platform info: {content.split(',')[0]}")
        
        return is_jetson
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_config():
    """Test configuration"""
    print("\n" + "=" * 60)
    print("5. Testing Configuration")
    print("=" * 60)
    try:
        import yaml
        from pathlib import Path
        
        config_file = Path('config.yaml')
        if not config_file.exists():
            print("✗ config.yaml not found")
            return False
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        cuda_enabled = config.get('use_cuda_motion_detection', False)
        hw_decode = config.get('use_hardware_decode', False)
        hw_encode = config.get('use_hardware_encode', False)
        
        print(f"  CUDA Motion Detection: {'✓ Enabled' if cuda_enabled else '✗ Disabled'}")
        print(f"  Hardware Decode: {'✓ Enabled' if hw_decode else '✗ Disabled'}")
        print(f"  Hardware Encode: {'✓ Enabled' if hw_encode else '✗ Disabled'}")
        print(f"  Detection Scale: {config.get('motion_detection_scale', 'N/A')}")
        print(f"  Frame Skip: {config.get('motion_frame_skip', 'N/A')}")
        
        if cuda_enabled and hw_decode and hw_encode:
            print("✓ Configuration optimized for Jetson")
            return True
        else:
            print("⚠ Configuration could be improved")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  JETSON ORIN OPTIMIZATION TEST")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("OpenCV CUDA", test_opencv_cuda()))
    results.append(("CUDA Motion Detector", test_cuda_motion_detector()))
    results.append(("FFmpeg Hardware", test_ffmpeg_hardware()))
    results.append(("Platform Detection", test_platform_detection()))
    results.append(("Configuration", test_config()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name:25s} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} tests passed")
    print("=" * 60 + "\n")
    
    if passed == total:
        print("🚀 All systems optimized! Ready for 5-8 concurrent streams!")
        print("\nNext steps:")
        print("  1. Edit config.yaml with your camera RTSP URLs")
        print("  2. Run: python3 app.py")
        print("  3. Monitor: sudo tegrastats or sudo jtop")
        return 0
    else:
        print("⚠ Some optimizations are not active")
        print("\nTroubleshooting:")
        if not results[0][1]:  # OpenCV CUDA
            print("  - Remove pip opencv: pip3 uninstall opencv-python")
            print("  - System OpenCV should have CUDA support")
        if not results[4][1]:  # Config
            print("  - Run: python3 detect_hardware.py")
            print("  - This will update config.yaml automatically")
        return 1

if __name__ == '__main__':
    sys.exit(main())
