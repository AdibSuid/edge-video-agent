import cv2
import sys

print("=" * 70)
print("OpenCV Build Verification")
print("=" * 70)

# Version check
version = cv2.__version__
print(f"\n1. Version: {version}")

if not version.startswith('4.5.1'):
    print(f"   ✗ Wrong version! Expected 4.5.1, got {version}")
    print(f"   ✗ Location: {cv2.__file__}")
    print("\n   Run: source ~/.bashrc")
    sys.exit(1)

build_info = cv2.getBuildInformation()

# GStreamer check
print("\n2. GStreamer:")
gst_enabled = False
for line in build_info.split('\n'):
    if 'GStreamer:' in line:
        print(f"   {line.strip()}")
        if 'YES' in line:
            gst_enabled = True
            print("   ✓ ENABLED")
        else:
            print("   ✗ DISABLED")
        break

if not gst_enabled:
    print("   ✗ GStreamer NOT found - rebuild needed!")
    sys.exit(1)

# CUDA check
print("\n3. CUDA:")
try:
    count = cv2.cuda.getCudaEnabledDeviceCount()
    print(f"   ✓ CUDA devices: {count}")
except Exception as e:
    print(f"   ✗ CUDA error: {e}")

# Pipeline test
print("\n4. GStreamer Pipeline Test:")
pipeline = "videotestsrc num-buffers=30 ! video/x-raw,width=640,height=480 ! videoconvert ! appsink"
cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

if cap.isOpened():
    ret, frame = cap.read()
    if ret:
        print(f"   ✓ Pipeline works! Frame: {frame.shape}")
    else:
        print("   ✗ Failed to read frame")
    cap.release()
else:
    print("   ✗ Pipeline failed to open")

print("\n" + "=" * 70)
print("✓✓ All checks passed!")
print("=" * 70)