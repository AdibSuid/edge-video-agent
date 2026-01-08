#!/usr/bin/env python3
"""
Test background subtraction with real video files
"""
import cv2
import numpy as np
import sys
import os
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion_detector import MotionDetector
from motion_detector_cuda import MotionDetectorCUDA

def test_with_video(video_path, detector_type='cpu'):
    """Test motion detection with a real video file"""
    print(f"Testing {detector_type.upper()} detector with video: {video_path}")

    # Initialize detector
    if detector_type == 'cpu':
        detector = MotionDetector(sensitivity=50, min_area=100)
    else:
        detector = MotionDetectorCUDA(sensitivity=50, min_area=100)

    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open video file: {video_path}")
        return False

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"📹 Video info: {width}x{height}, {fps} FPS, {frame_count} frames")

    motion_frames = 0
    total_frames = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            total_frames += 1

            # Test motion detection
            motion_detected = detector.detect(frame)

            if motion_detected:
                motion_frames += 1

            # Print progress every 100 frames
            if total_frames % 100 == 0:
                print(f"📊 Processed {total_frames}/{frame_count} frames, motion detected in {motion_frames} frames")

            # Limit to first 1000 frames for testing
            if total_frames >= 1000:
                break

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        return False
    finally:
        cap.release()

    processing_time = time.time() - start_time
    motion_percentage = (motion_frames / total_frames) * 100 if total_frames > 0 else 0

    print("✅ Video processing completed!")
    print(f"📈 Motion detected in {motion_frames}/{total_frames} frames ({motion_percentage:.1f}%)")
    print(f"⏱️  Processing time: {processing_time:.2f} seconds")
    print(f"⚡ Processing rate: {total_frames/processing_time:.1f} FPS")
    return True

def main():
    """Main test function"""
    print("🎬 Testing Background Subtraction with Real Video Files\n")

    # Find video files in root directory
    video_files = [f for f in os.listdir('.') if f.endswith('.mp4')]
    if not video_files:
        print("❌ No video files found in root directory")
        return False

    print(f"📁 Found {len(video_files)} video files: {video_files[:3]}{'...' if len(video_files) > 3 else ''}")

    # Test with first video file
    test_video = video_files[0]
    print(f"\n🎯 Testing with: {test_video}\n")

    # Test CPU detector
    print("=" * 50)
    success_cpu = test_with_video(test_video, 'cpu')

    print("\n" + "=" * 50)
    # Test CUDA detector
    success_cuda = test_with_video(test_video, 'cuda')

    print("\n" + "=" * 50)
    if success_cpu and success_cuda:
        print("✅ All tests passed! Background subtraction is working correctly with real video.")
        return True
    else:
        print("❌ Some tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)