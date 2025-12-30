# Jetson TX2 NX JetPack 4 - Hardware Acceleration Setup

This guide helps you enable hardware encoding and decoding on Jetson TX2 NX with JetPack 4.

## Requirements

### 1. JetPack Version
- **Required**: JetPack 4.6+ (L4T 32.6+)
- Check version: `cat /etc/nv_tegra_release`

### 2. GStreamer (for Hardware Decode)

#### Check if installed:
```bash
gst-inspect-1.0 --version
gst-inspect-1.0 omxh264dec
```

#### Install if missing:
```bash
sudo apt-get update
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-omx-generic \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev
```

### 3. OpenCV with GStreamer Support (for Hardware Decode)

#### Check if OpenCV has GStreamer support:
```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer
```

Should show: `GStreamer: YES`

#### If GStreamer support is missing, rebuild OpenCV:
```bash
# Install dependencies
sudo apt-get install -y \
    build-essential cmake git \
    libgtk2.0-dev pkg-config \
    libavcodec-dev libavformat-dev libswscale-dev \
    libtbb2 libtbb-dev libjpeg-dev libpng-dev libtiff-dev \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev

# Build OpenCV with GStreamer (this takes 1-2 hours on TX2)
cd ~
git clone https://github.com/opencv/opencv.git
cd opencv
git checkout 4.5.5  # Stable version for JP4

mkdir build && cd build
cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    -D WITH_CUDA=ON \
    -D WITH_CUBLAS=ON \
    -D CUDA_ARCH_BIN="6.2" \
    -D CUDA_ARCH_PTX="" \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_TBB=ON \
    -D BUILD_opencv_python3=ON \
    -D PYTHON3_EXECUTABLE=$(which python3) \
    ..

make -j4  # Use all 4 cores
sudo make install
sudo ldconfig
```

### 4. FFmpeg with NVENC Support (for Hardware Encode)

#### Check if FFmpeg has NVENC:
```bash
ffmpeg -encoders 2>/dev/null | grep nvenc
ffmpeg -encoders 2>/dev/null | grep omx
```

Should show either `h264_nvenc` or `h264_omx`

#### Option A: Use system FFmpeg with OMX (easier):
```bash
sudo apt-get install -y ffmpeg
```

#### Option B: Build FFmpeg with NVENC (better performance):
```bash
# Install dependencies
sudo apt-get install -y \
    build-essential yasm cmake git \
    libx264-dev libx265-dev libnuma-dev

# Clone and build FFmpeg with NVENC
cd ~
git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg-nvenc
cd ffmpeg-nvenc
git checkout release/4.4

# Configure with NVIDIA headers
./configure \
    --enable-cuda \
    --enable-cuvid \
    --enable-nvenc \
    --enable-nonfree \
    --enable-libnpp \
    --extra-cflags=-I/usr/local/cuda/include \
    --extra-ldflags=-L/usr/local/cuda/lib64 \
    --enable-gpl \
    --enable-libx264

make -j4
sudo make install
sudo ldconfig
```

### 5. Verify Installation

Run the diagnostic script:
```bash
chmod +x check_jetpack4_hardware.sh
./check_jetpack4_hardware.sh
```

Expected output:
- ✓ omxh264dec available (for decode)
- ✓ h264_nvenc OR h264_omx available (for encode)
- OpenCV with GStreamer: YES

## Key Differences: JetPack 4 vs JetPack 5

| Feature | JetPack 4 (TX2 NX) | JetPack 5 (Orin) |
|---------|-------------------|------------------|
| **Decode GStreamer** | `omxh264dec` | `nvv4l2decoder` |
| **Encode GStreamer** | `omxh264enc` | `nvv4l2h264enc` |
| **FFmpeg Decode** | `h264_cuvid` (limited) | `h264_cuvid` |
| **FFmpeg Encode** | `h264_nvenc` or `h264_omx` | `h264_nvenc` |
| **API** | OpenMAX (OMX) | V4L2 |

## Testing Hardware Decode

Test GStreamer hardware decode:
```bash
gst-launch-1.0 rtspsrc location=rtsp://admin:password@192.168.1.100:554/stream ! \
    rtph264depay ! h264parse ! omxh264dec ! videoconvert ! autovideosink
```

## Testing Hardware Encode

Test FFmpeg hardware encode:
```bash
# With NVENC (if available)
ffmpeg -f lavfi -i testsrc=duration=10:size=1920x1080:rate=30 \
    -c:v h264_nvenc -preset fast test_nvenc.mp4

# With OMX (fallback)
ffmpeg -f lavfi -i testsrc=duration=10:size=1920x1080:rate=30 \
    -c:v h264_omx -b:v 2M test_omx.mp4
```

## Troubleshooting

### Issue: "omxh264dec not found"
**Solution**: Install GStreamer OMX plugins:
```bash
sudo apt-get install gstreamer1.0-omx-generic
```

### Issue: "h264_nvenc not found"
**Solution**: Either:
1. Use `h264_omx` instead (built into JetPack 4)
2. Build FFmpeg with NVENC support (see Option B above)

### Issue: OpenCV can't open GStreamer pipeline
**Solution**: Rebuild OpenCV with GStreamer support (see step 3)

### Issue: "Could not load library libnvbufsurface.so"
**Solution**: Add NVIDIA libs to path:
```bash
echo 'export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/tegra:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

## Performance Expectations

**TX2 NX Hardware Specs:**
- GPU: 256-core Pascal GPU
- Video Encode: 1x 4K30 or 2x 1080p60
- Video Decode: 1x 4K60 or 4x 1080p30
- Recommended concurrent streams: 2-4 cameras

**Settings for TX2 NX:**
```yaml
use_hardware_decode: true
use_hardware_encode: true
motion_detection_scale: 0.25
motion_frame_skip: 2
chunk_fps: 2
encoding_preset: ultrafast
```
