# Step-by-Step Guide: Enable Full Hardware Acceleration on TX2 NX

**Target System**: Jetson TX2 NX with JetPack 4.5.1 (L4T 32.5.1)
**Goal**: Hardware-accelerated decode AND encode using GStreamer
**Time Required**: 2-3 hours (mostly build time)

## Overview

This guide will:
1. ✅ Check your current setup
2. ✅ Install dependencies
3. ✅ Rebuild OpenCV with GStreamer support (~2 hours)
4. ✅ Update your code to use GStreamer encoding
5. ✅ Test hardware acceleration

---

## STEP 1: Check Current System (5 minutes)

Run these commands on your TX2 NX:

```bash
# Navigate to your project
cd /path/to/edge-video-agent

# Run compatibility test
chmod +x test_tx2_compatibility.sh
./test_tx2_compatibility.sh
```

**What to look for:**
- ✓ nvv4l2decoder: Available (should be YES)
- ✓ nvv4l2h264enc: Available (should be YES)
- ✗ OpenCV GStreamer Support: NO (this is what we'll fix)

**Save the output** - we'll compare after the fix.

---

## STEP 2: Install Dependencies (10 minutes)

```bash
# Update system
sudo apt-get update

# Install GStreamer development libraries
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Install OpenCV build dependencies
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    pkg-config \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    python3-dev \
    python3-numpy

# Install additional libraries for better performance
sudo apt-get install -y \
    libtbb2 \
    libtbb-dev \
    libdc1394-22-dev

# Verify GStreamer is installed correctly
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc
```

**Expected**: Both commands should show plugin information.

---

## STEP 3: Backup Current OpenCV (2 minutes)

```bash
# Check current OpenCV version
python3 -c "import cv2; print('Current OpenCV:', cv2.__version__)"

# If you installed via pip, uninstall it
pip3 uninstall -y opencv-python opencv-contrib-python opencv-python-headless

# Backup any existing system OpenCV (optional)
# We'll be installing to /usr/local, so shouldn't conflict
```

---

## STEP 4: Download and Build OpenCV (90-120 minutes)

This is the longest step - the TX2 NX will compile for ~2 hours.

```bash
# Create workspace
mkdir -p ~/opencv_build
cd ~/opencv_build

# Download OpenCV 4.5.5 (tested on JetPack 4.5.1)
wget -O opencv.zip https://github.com/opencv/opencv/archive/4.5.5.zip
unzip opencv.zip

# Download OpenCV contrib modules (optional but recommended)
wget -O opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/4.5.5.zip
unzip opencv_contrib.zip

# Create build directory
cd opencv-4.5.5
mkdir build
cd build

# Configure CMake with GStreamer support
cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-4.5.5/modules \
    -D EIGEN_INCLUDE_PATH=/usr/include/eigen3 \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN="6.2" \
    -D CUDA_ARCH_PTX="" \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_CUBLAS=ON \
    -D WITH_LIBV4L=ON \
    -D WITH_V4L=ON \
    -D BUILD_opencv_python3=ON \
    -D BUILD_opencv_python2=OFF \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_EXAMPLES=OFF \
    -D WITH_QT=OFF \
    -D WITH_GTK=ON \
    -D WITH_OPENGL=ON \
    -D WITH_TBB=ON \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    -D PYTHON3_INCLUDE_DIR=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())") \
    -D PYTHON3_PACKAGES_PATH=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())") \
    ..

# IMPORTANT: Check CMake output
echo ""
echo "=========================================="
echo "CHECK THESE BEFORE CONTINUING:"
echo "=========================================="
echo "Look for these lines in the output above:"
echo "  GStreamer: YES"
echo "  CUDA: YES"
echo "  Python 3:"
echo "    Interpreter: /usr/bin/python3"
echo ""
echo "If GStreamer shows NO, something is wrong!"
echo "Press Ctrl+C to abort, or Enter to continue..."
read
```

**CRITICAL**: Before proceeding, verify CMake output shows:
```
--   Video I/O:
--     GStreamer:                   YES (1.14.5)
--     v4l/v4l2:                    YES (linux/videodev2.h)
--
--   NVIDIA CUDA:                   YES (ver 10.2)
```

If GStreamer shows NO, stop and troubleshoot.

```bash
# Build OpenCV (uses all 4 cores, takes ~2 hours)
make -j4

# If build fails with memory errors, try:
# make -j2  # Use only 2 cores

# Install OpenCV
sudo make install
sudo ldconfig

# Verify installation
python3 -c "import cv2; print('OpenCV Version:', cv2.__version__)"

# VERIFY GSTREAMER SUPPORT (CRITICAL!)
python3 -c "import cv2; import sys; info = cv2.getBuildInformation(); has_gs = 'GStreamer' in info and 'YES' in info.split('GStreamer')[1].split('\n')[0]; print('GStreamer support:', 'YES ✓' if has_gs else 'NO ✗'); sys.exit(0 if has_gs else 1)"
```

**Expected output:**
```
OpenCV Version: 4.5.5
GStreamer support: YES ✓
```

**If you see `NO ✗`**: Something went wrong. Don't continue - the hardware decode won't work.

---

## STEP 5: Test Hardware Decode (5 minutes)

```bash
# Test GStreamer decoder directly
gst-launch-1.0 -e videotestsrc num-buffers=300 ! \
    'video/x-raw,width=1920,height=1080,framerate=30/1' ! \
    x264enc ! h264parse ! nvv4l2decoder ! fakesink

# Test with OpenCV
python3 << 'EOF'
import cv2

# GStreamer pipeline
pipeline = (
    "videotestsrc num-buffers=100 ! "
    "video/x-raw,width=1920,height=1080,framerate=30/1 ! "
    "x264enc ! h264parse ! nvv4l2decoder ! "
    "nvvidconv ! video/x-raw,format=BGRx ! "
    "videoconvert ! video/x-raw,format=BGR ! appsink"
)

print("Testing hardware decode with OpenCV + GStreamer...")
cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("✗ FAILED: Could not open GStreamer pipeline")
    exit(1)

frames = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    frames += 1

cap.release()
print(f"✓ SUCCESS: Decoded {frames} frames using hardware")
EOF
```

**Expected**: `✓ SUCCESS: Decoded 100 frames using hardware`

---

## STEP 6: Update Code for GStreamer Encoding (15 minutes)

Now we'll update `streamer.py` to use GStreamer for encoding instead of FFmpeg.

### 6.1: Create New Encoding Method

```bash
# Backup your current streamer.py
cp streamer.py streamer.py.backup

# Open streamer.py in your editor
nano streamer.py  # or vim, or code
```

### 6.2: Replace the `_encode_chunk_hardware` Method

Find the `_encode_chunk_hardware` method (around line 178) and **replace it entirely** with this GStreamer version:

```python
def _encode_chunk_hardware(self, frames, out_path, fps):
    """
    Encode video chunk using GStreamer with nvv4l2h264enc (community standard).

    This is the NVIDIA-recommended approach for Jetson platforms.
    Uses hardware-accelerated encoding via V4L2 API.
    """
    try:
        import cv2
        import subprocess

        if not frames:
            return False

        h, w = frames[0].shape[:2]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if we're on Jetson
        is_jetson = os.path.exists('/etc/nv_tegra_release') or os.path.exists('/sys/module/tegra_fuse')

        if not is_jetson:
            self.logger.warning("Hardware encoding only supported on Jetson, using software")
            return False

        # Build GStreamer pipeline for hardware encoding
        # This is the community standard method from NVIDIA documentation
        gst_cmd = [
            'gst-launch-1.0',
            '-e',  # Send EOS on interrupt
            'fdsrc', '!',
            f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
            'videoconvert', '!',
            'video/x-raw,format=I420', '!',
            'nvv4l2h264enc',
            'maxperf-enable=true',        # Enable maximum performance mode
            'bitrate=2000000',             # 2 Mbps
            'preset-level=1',              # 0=Slow, 1=Medium, 2=Fast, 3=UltraFast
            'insert-sps-pps=true',         # Insert SPS/PPS at every IDR
            'idrinterval=30', '!',         # IDR frame interval
            'h264parse', '!',
            'qtmux', '!',
            f'filesink location={out_path}'
        ]

        self.logger.info(f"Encoding with nvv4l2h264enc (GStreamer): {w}x{h} @ {fps}fps")

        # Start GStreamer subprocess
        proc = subprocess.Popen(
            gst_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**8
        )

        # Write frames to GStreamer stdin
        frames_written = 0
        for frame in frames:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.write(frame.tobytes())
                    frames_written += 1
                else:
                    self.logger.debug("GStreamer stdin closed prematurely")
                    break
            except (BrokenPipeError, IOError) as e:
                self.logger.debug(f"GStreamer pipe broken: {e}")
                break

        # Close stdin and wait for encoding to complete
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.flush()
                proc.stdin.close()
        except Exception as e:
            self.logger.debug(f"Error closing stdin: {e}")
            pass

        # Wait for GStreamer to finish
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            self.logger.warning("GStreamer encoding timeout")

        # Check success
        success = proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0

        if success:
            file_size = out_path.stat().st_size
            self.logger.info(f"✓ Hardware encoding succeeded: {out_path.name} ({file_size} bytes, {frames_written} frames)")
        else:
            self.logger.warning(f"✗ Hardware encoding failed (returncode={proc.returncode})")
            if stderr:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                self.logger.debug(f"GStreamer stderr: {error_msg}")
            # Clean up partial file
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception:
                    pass

        return success

    except Exception as e:
        self.logger.error(f"GStreamer hardware encoding error: {e}")
        import traceback
        self.logger.debug(traceback.format_exc())
        return False
```

### 6.3: Update the Chunking Loop (Optional but Recommended)

Find the `_chunking_loop` method around line 151-156 and update the fallback message:

```python
# Around line 156, change:
if not success:
    self.logger.warning("Hardware encoding failed, falling back to software encoding")
    # Remove any partial file from failed hardware encoding
    if out_path.exists():
        try:
            out_path.unlink()
        except Exception as e:
            self.logger.debug(f"Could not remove partial file: {e}")
    success = self._encode_chunk_software(frames, out_path, chunk_fps)
```

Save the file.

---

## STEP 7: Test the Complete System (10 minutes)

### 7.1: Test GStreamer Encoding Standalone

```bash
# Test encoding directly with GStreamer
python3 << 'EOF'
import cv2
import numpy as np
import subprocess
from pathlib import Path

# Generate test frames
frames = []
for i in range(60):  # 60 frames at 2 fps = 30 seconds
    frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    frames.append(frame)

h, w = frames[0].shape[:2]
fps = 2
out_path = Path('/tmp/test_gstreamer_encode.mp4')

print(f"Testing GStreamer encoding: {len(frames)} frames, {w}x{h} @ {fps}fps")

# GStreamer command
gst_cmd = [
    'gst-launch-1.0', '-e',
    'fdsrc', '!',
    f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
    'videoconvert', '!',
    'video/x-raw,format=I420', '!',
    'nvv4l2h264enc',
    'maxperf-enable=true',
    'bitrate=2000000',
    'preset-level=1', '!',
    'h264parse', '!',
    'qtmux', '!',
    f'filesink location={out_path}'
]

proc = subprocess.Popen(gst_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Write frames
for frame in frames:
    proc.stdin.write(frame.tobytes())

proc.stdin.close()
proc.wait()

if out_path.exists() and out_path.stat().st_size > 0:
    print(f"✓ SUCCESS: Encoded to {out_path} ({out_path.stat().st_size} bytes)")
    print(f"  Verify with: ffplay {out_path}")
else:
    print("✗ FAILED: Encoding did not produce valid file")
    stderr = proc.stderr.read().decode('utf-8', errors='ignore')
    print(f"Error: {stderr[:500]}")
EOF
```

**Expected**: `✓ SUCCESS: Encoded to /tmp/test_gstreamer_encode.mp4`

### 7.2: Run Full Compatibility Test Again

```bash
# Run the test again
./test_tx2_compatibility.sh
```

**Expected output:**
```
OpenCV GStreamer Support: ✓ YES
nvv4l2decoder: ✓ Available
nvv4l2h264enc: ✓ Available

Hardware Decode: ✓ WILL WORK
Hardware Encode: ✓ WILL WORK (via GStreamer)
```

### 7.3: Test Your Application

```bash
# Start your application
python3 app.py
```

**Check logs for:**
```
Detected hardware config: v4l2 (JetPack 4.x)
Starting hardware-accelerated decode pipeline with GStreamer
GStreamer hardware decode pipeline opened successfully
Encoding with nvv4l2h264enc (GStreamer): 1920x1080 @ 2fps
✓ Hardware encoding succeeded: chunk.mp4 (XXX bytes, YY frames)
```

---

## STEP 8: Verify Performance (5 minutes)

```bash
# Monitor CPU and GPU usage while app is running
# Open a new terminal on TX2 NX

# Monitor CPU (should be low, <30%)
htop

# Monitor GPU (should show activity)
tegrastats

# Expected stats with hardware acceleration:
# CPU: 15-30% (low because hardware does the work)
# GPU: Active
# EMC: Active (memory controller)
```

**Performance benchmarks you should see:**
- Hardware decode: 1080p @ 30fps, ~10% CPU
- Hardware encode: 1080p @ 25fps, ~15% CPU
- Software decode: 1080p @ 5-10fps, ~70% CPU
- Software encode: 1080p @ 5fps, ~90% CPU

---

## Troubleshooting

### Issue 1: OpenCV Build Fails with "No Space Left"

```bash
# TX2 NX has limited storage, clean up first
sudo apt-get clean
sudo apt-get autoremove
df -h  # Check available space, need at least 5GB

# Or build with fewer cores
make -j2  # Instead of -j4
```

### Issue 2: CMake Shows "GStreamer: NO"

```bash
# Check if GStreamer dev packages are installed
dpkg -l | grep gstreamer

# Reinstall if missing
sudo apt-get install --reinstall \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Re-run cmake
cd ~/opencv_build/opencv-4.5.5/build
rm -rf *
cmake ... (same command as before)
```

### Issue 3: GStreamer Encoding Fails with "Could not create element"

```bash
# Verify nvv4l2h264enc exists
gst-inspect-1.0 nvv4l2h264enc

# If not found, install
sudo apt-get install gstreamer1.0-plugins-bad
```

### Issue 4: Application Still Uses Software Encoding

```bash
# Check logs
tail -f logs/your_stream_id.log

# Look for:
# "Encoding with nvv4l2h264enc" ✓ Good
# "Hardware encoding failed" ✗ Bad

# If failing, test encoding standalone (Step 7.1)
```

---

## Success Criteria

You've successfully completed the fix when:

1. ✅ `./test_tx2_compatibility.sh` shows all green checks
2. ✅ OpenCV GStreamer support: YES
3. ✅ Application logs show: "Encoding with nvv4l2h264enc"
4. ✅ Application logs show: "✓ Hardware encoding succeeded"
5. ✅ CPU usage < 30% during operation
6. ✅ Video chunks are created successfully

---

## Quick Reference Commands

```bash
# Check OpenCV GStreamer support
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep GStreamer

# Test hardware decoder
gst-launch-1.0 videotestsrc num-buffers=100 ! x264enc ! nvv4l2decoder ! fakesink

# Test hardware encoder
gst-launch-1.0 videotestsrc num-buffers=100 ! nvv4l2h264enc ! fakesink

# Monitor performance
tegrastats

# View logs
tail -f logs/*.log
```

---

## Estimated Time Breakdown

- Step 1-2: Install dependencies (15 min)
- Step 3-4: Build OpenCV (120 min) ⏰ **Longest step**
- Step 5: Test decode (5 min)
- Step 6: Update code (15 min)
- Step 7-8: Test and verify (15 min)

**Total: ~2.5 hours** (mostly waiting for OpenCV build)

---

## Next Steps After Success

1. Update `config.yaml` to ensure hardware acceleration is enabled:
   ```yaml
   use_hardware_decode: true
   use_hardware_encode: true
   ```

2. Consider optimizing GStreamer encoder settings:
   ```python
   'preset-level=3',  # UltraFast (lower quality, faster)
   'profile=0',       # Baseline profile
   'bitrate=3000000', # Increase bitrate for better quality
   ```

3. Test with real RTSP cameras

4. Monitor long-term stability

Good luck! 🚀
