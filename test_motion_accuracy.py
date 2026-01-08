#!/usr/bin/env python3
"""
Test background subtraction with motion.mp4 and nomotion.mp4
"""
import cv2
import numpy as np
import sys
import os
import time

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion_detector import MotionDetector

def test_video_file(video_path, expected_motion=True, max_frames=300):
    """Test a specific video file for motion detection"""
    print(f"🎬 Testing: {video_path}")
    print(f"📋 Expected: {'Motion' if expected_motion else 'No Motion'}")

    # Initialize detector with appropriate sensitivity
    detector = MotionDetector(sensitivity=30, min_area=50)

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

    print(f"📹 Video info: {width}x{height}, {fps:.1f} FPS, {frame_count} frames")

    motion_frames = 0
    total_frames = 0
    start_time = time.time()

    try:
        while total_frames < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            total_frames += 1

            # Test motion detection
            motion_detected = detector.detect(frame)

            if motion_detected:
                motion_frames += 1

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        return False
    finally:
        cap.release()

    processing_time = time.time() - start_time
    motion_percentage = (motion_frames / total_frames) * 100 if total_frames > 0 else 0

    print("✅ Video processing completed!")
    print(f"📈 Results: {motion_frames}/{total_frames} frames with motion ({motion_percentage:.1f}%)")
    print(f"⏱️  Processing time: {processing_time:.2f} seconds")
    print(f"⚡ Processing rate: {total_frames/processing_time:.1f} FPS")

    # Validate results
    if expected_motion:
        # Should detect motion in at least 10% of frames
        success = motion_percentage >= 10.0
        result = "✅ PASS" if success else "❌ FAIL"
        print(f"{result}: Motion detected ({motion_percentage:.1f}% >= 10%)")
    else:
        # Should detect motion in less than 5% of frames
        success = motion_percentage < 5.0
        result = "✅ PASS" if success else "❌ FAIL"
        print(f"{result}: No motion detected ({motion_percentage:.1f}% < 5%)")

    return success

def analyze_frame_differences(video_file):
    """Analyze raw frame differences to understand the video content"""
    print(f"🔍 Analyzing frame differences in {video_file}")

    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        print(f"❌ Could not open {video_file}")
        return

    # Read first frame
    ret, prev_frame = cap.read()
    if not ret:
        print("❌ Could not read first frame")
        return

    # Convert to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (5, 5), 0)

    frame_count = 1
    total_diff = 0
    motion_frames = 0
    diffs = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Convert to grayscale and blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # Calculate absolute difference
        diff = cv2.absdiff(prev_gray, gray)
        mean_diff = np.mean(diff)
        diffs.append(mean_diff)

        # Simple threshold for motion detection
        if mean_diff > 5.0:  # Threshold for motion
            motion_frames += 1

        total_diff += mean_diff
        prev_gray = gray
        frame_count += 1

        if frame_count > 100:  # Limit analysis to first 100 frames
            break

    cap.release()

    avg_diff = total_diff / frame_count
    motion_percentage = (motion_frames / frame_count) * 100

    print(".2f")
    print(".2f")
    print(".2f")
    print(".2f")

    return avg_diff, motion_percentage


def main():
    """Main test function"""
    print("🎯 Testing Motion Detection Accuracy\n")
    print("Testing MOG2 background subtraction with noise filtering on known motion/no-motion videos\n")

    # First analyze raw frame differences
    print("=" * 60)
    print("🔬 RAW FRAME DIFFERENCE ANALYSIS")
    print("=" * 60)

    test_cases = [
        ("nomotion.mp4", False),  # Should detect NO motion
        ("motion.mp4", True)      # Should detect MOTION
    ]

    for video_file, _ in test_cases:
        if os.path.exists(video_file):
            analyze_frame_differences(video_file)
            print()

    print("=" * 60)
    print("🎯 MOG2 BACKGROUND SUBTRACTION TESTS")
    print("=" * 60)

    results = []

    for video_file, expected_motion in test_cases:
        if os.path.exists(video_file):
            print("=" * 60)
            success = test_video_file(video_file, expected_motion)
            results.append(success)
            print()
        else:
            print(f"❌ Test file not found: {video_file}")
            results.append(False)

    print("=" * 60)
    print("📊 FINAL RESULTS:")

    if all(results):
        print("✅ ALL TESTS PASSED! MOG2 background subtraction is working correctly.")
        print("🎉 Motion detection accurately distinguishes between motion and no-motion videos!")
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        for i, (video_file, expected_motion) in enumerate(test_cases):
            status = "✅ PASS" if results[i] else "❌ FAIL"
            expected = "Motion" if expected_motion else "No Motion"
            print(f"  {status}: {video_file} ({expected})")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)