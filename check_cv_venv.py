#!/usr/bin/env python3
# Check OpenCV from venv
import sys
print("Python executable:", sys.executable)
print("Python path:", sys.path[:3])
print()

try:
    import cv2
    print("OpenCV version:", cv2.__version__)
    print("OpenCV file:", cv2.__file__)
    cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
    print("CUDA devices:", cuda_count)
    print("CUDA available:", cuda_count > 0)
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()
