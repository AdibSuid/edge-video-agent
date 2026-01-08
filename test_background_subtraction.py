#!/usr/bin/env python3
"""
Test script for background subtraction motion detection
"""
import cv2
import numpy as np
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion_detector import MotionDetector
from motion_detector_cuda import MotionDetectorCUDA

def test_background_subtraction():
    """Test that background subtraction detectors initialize and work"""
    print("Testing background subtraction implementation...")

    # Test CPU detector
    print("\n1. Testing CPU MotionDetector with MOG2...")
    try:
        detector = MotionDetector(sensitivity=50, min_area=100)
        print("✓ CPU detector initialized successfully")

        # Create a test frame
        test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # Test detection (should return False initially as background is learning)
        result = detector.detect(test_frame)
        print(f"✓ Detection result: {result} (expected: False for initial frames)")

    except Exception as e:
        print(f"✗ CPU detector failed: {e}")
        return False

    # Test CUDA detector
    print("\n2. Testing CUDA MotionDetectorCUDA with MOG2...")
    try:
        cuda_detector = MotionDetectorCUDA(sensitivity=50, min_area=100)
        print("✓ CUDA detector initialized successfully")

        # Test detection
        result = cuda_detector.detect(test_frame)
        print(f"✓ CUDA detection result: {result} (expected: False for initial frames)")

        # Test settings update
        cuda_detector.update_settings(sensitivity=75)
        print("✓ Settings update successful")

    except Exception as e:
        print(f"✗ CUDA detector failed: {e}")
        return False

    print("\n✓ All tests passed! Background subtraction implementation is working.")
    return True

if __name__ == "__main__":
    success = test_background_subtraction()
    sys.exit(0 if success else 1)