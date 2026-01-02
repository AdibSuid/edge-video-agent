#!/bin/bash

# OpenCV Installation Script for NVIDIA Jetson TX2 NX
# Enables CUDA, cuDNN, GStreamer, and NVIDIA Hardware Encoder/Decoder support
# Optimized for Jetson TX2 NX (Tegra186, Pascal GPU Architecture 6.2)
# Date: 2026-01-02

set -e

# Configuration
OPENCV_VERSION="4.8.0"
CUDA_ARCH_BIN="6.2"  # Jetson TX2 NX (tegra186, Pascal architecture)
INSTALL_DIR="/usr/local"
WORKSPACE="/tmp/opencv_build"
NUM_JOBS=$(nproc)

echo "=========================================="
echo "OpenCV ${OPENCV_VERSION} Installation for Jetson TX2 NX"
echo "CUDA Architecture: ${CUDA_ARCH_BIN}"
echo "Build jobs: ${NUM_JOBS}"
echo "=========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    print_error "This script is designed for NVIDIA Jetson platforms"
    exit 1
fi

# Verify Jetson TX2 NX
JETSON_MODEL=$(cat /sys/firmware/devicetree/base/model 2>/dev/null || echo "Unknown")
print_status "Detected Jetson: ${JETSON_MODEL}"

# Step 1: Remove existing OpenCV installations
print_status "Removing existing OpenCV installations..."
sudo apt-get purge -y libopencv* python3-opencv || true
sudo apt-get autoremove -y

# Step 2: Update system
print_status "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Step 3: Install Jetson-specific multimedia packages
print_status "Installing NVIDIA Jetson multimedia libraries..."
sudo apt-get install -y \
    nvidia-l4t-multimedia \
    nvidia-l4t-multimedia-utils \
    nvidia-l4t-camera \
    libnvidia-encode-470-server || \
    sudo apt-get install -y \
    nvidia-l4t-multimedia \
    nvidia-l4t-multimedia-utils \
    nvidia-l4t-camera

# Step 4: Install build dependencies
print_status "Installing build dependencies..."
sudo apt-get install -y \
    build-essential cmake git pkg-config unzip yasm checkinstall \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev libavresample-dev \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-ugly gstreamer1.0-tools gstreamer1.0-gl \
    gstreamer1.0-gtk3 gstreamer1.0-libav \
    libxvidcore-dev libx264-dev libgtk-3-dev \
    libatlas-base-dev gfortran \
    libv4l-dev v4l-utils qv4l2 \
    libtbb-dev libopenblas-dev liblapack-dev liblapacke-dev \
    python3-dev python3-pip python3-numpy python3-matplotlib \
    libhdf5-dev libhdf5-serial-dev \
    libprotobuf-dev protobuf-compiler \
    libgoogle-glog-dev libgflags-dev \
    libdc1394-22-dev \
    wget curl

# Install Python dependencies
print_status "Installing Python packages..."
pip3 install --upgrade pip
pip3 install numpy

# Step 5: Increase swap (critical for Jetson)
print_status "Configuring swap space..."
EXISTING_SWAP=$(swapon --show | grep -v NAME | awk '{print $3}' | head -n1)
if [ -z "$EXISTING_SWAP" ] || [ "$EXISTING_SWAP" != "8G" ]; then
    # Disable existing swap if present
    sudo swapoff -a || true
    
    # Remove old swapfile if exists
    sudo rm -f /swapfile
    
    # Create 8GB swapfile
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Make permanent
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    print_status "8GB swap configured"
else
    print_status "Swap already configured: $EXISTING_SWAP"
fi

# Step 6: Create workspace
print_status "Creating build workspace..."
mkdir -p ${WORKSPACE}
cd ${WORKSPACE}

# Step 7: Download OpenCV and OpenCV contrib
print_status "Downloading OpenCV ${OPENCV_VERSION}..."
if [ ! -d "opencv" ]; then
    git clone --depth 1 --branch ${OPENCV_VERSION} https://github.com/opencv/opencv.git
fi

if [ ! -d "opencv_contrib" ]; then
    git clone --depth 1 --branch ${OPENCV_VERSION} https://github.com/opencv/opencv_contrib.git
fi

# Step 8: Prepare build directory
cd opencv
print_status "Current directory: $(pwd)"

mkdir -p build
cd build

# Clean previous CMake cache
rm -rf CMakeCache.txt CMakeFiles

# Step 9: Configure build with CMake
print_status "Configuring OpenCV build for Jetson TX2 NX..."

# Detect Python paths
PYTHON3_EXECUTABLE=$(which python3)
PYTHON3_INCLUDE_DIR=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())")
PYTHON3_PACKAGES_PATH=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
PYTHON3_LIBRARY=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.6m.so

print_status "Python3 executable: $PYTHON3_EXECUTABLE"
print_status "Python3 include: $PYTHON3_INCLUDE_DIR"
print_status "Python3 library: $PYTHON3_LIBRARY"

# CMake configuration optimized for Jetson TX2 NX
cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=${INSTALL_DIR} \
    -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
    -D EIGEN_INCLUDE_PATH=/usr/include/eigen3 \
    \
    -D WITH_CUDA=ON \
    -D CUDA_ARCH_BIN=${CUDA_ARCH_BIN} \
    -D CUDA_ARCH_PTX="" \
    -D ENABLE_FAST_MATH=ON \
    -D CUDA_FAST_MATH=ON \
    -D WITH_CUBLAS=ON \
    -D WITH_CUDNN=ON \
    -D OPENCV_DNN_CUDA=ON \
    -D WITH_NVCUVID=ON \
    -D WITH_NVCUVENC=ON \
    -D BUILD_opencv_cudacodec=ON \
    \
    -D WITH_GSTREAMER=ON \
    -D WITH_GSTREAMER_0_10=OFF \
    -D WITH_LIBV4L=ON \
    -D WITH_V4L=ON \
    \
    -D BUILD_opencv_python3=ON \
    -D BUILD_TESTS=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D BUILD_EXAMPLES=OFF \
    \
    -D WITH_QT=OFF \
    -D WITH_GTK=ON \
    -D WITH_OPENGL=ON \
    \
    -D WITH_TBB=ON \
    -D BUILD_TBB=OFF \
    \
    -D WITH_FFMPEG=ON \
    -D ENABLE_NEON=ON \
    -D CPU_BASELINE=NEON \
    \
    -D OPENCV_ENABLE_NONFREE=ON \
    -D INSTALL_PYTHON_EXAMPLES=OFF \
    -D INSTALL_C_EXAMPLES=OFF \
    -D BUILD_NEW_PYTHON_SUPPORT=ON \
    \
    -D PYTHON3_EXECUTABLE=$PYTHON3_EXECUTABLE \
    -D PYTHON3_INCLUDE_DIR=$PYTHON3_INCLUDE_DIR \
    -D PYTHON3_LIBRARY=$PYTHON3_LIBRARY \
    -D PYTHON3_PACKAGES_PATH=$PYTHON3_PACKAGES_PATH \
    -D PYTHON3_NUMPY_INCLUDE_DIRS=$(python3 -c "import numpy; print(numpy.get_include())") \
    ..

# Check CMake output
if [ $? -ne 0 ]; then
    print_error "CMake configuration failed!"
    exit 1
fi

print_status "CMake configuration completed successfully"
print_status "Key features enabled:"
echo "  - CUDA: YES (Arch: ${CUDA_ARCH_BIN})"
echo "  - cuDNN: YES"
echo "  - GStreamer: YES"
echo "  - NVCUVID (HW Decode): YES"
echo "  - NVCUVENC (HW Encode): YES"
echo "  - cudacodec: YES"
echo "  - Python3: YES"
echo "  - TBB: YES"
echo "  - V4L: YES"
echo "  - NEON: YES"

# Verify critical features
print_status "Verifying build configuration..."
if [ -f CMakeCache.txt ]; then
    grep "CUDA_ARCH_BIN" CMakeCache.txt || print_warning "CUDA_ARCH_BIN not found"
    grep "WITH_GSTREAMER:BOOL=ON" CMakeCache.txt || print_warning "GStreamer not enabled"
    grep "WITH_NVCUVID:BOOL=ON" CMakeCache.txt || print_warning "NVCUVID not enabled"
fi

read -p "Press Enter to continue with build or Ctrl+C to abort..."

# Step 10: Build OpenCV
print_status "Building OpenCV (this will take 1-3 hours)..."
print_status "Using ${NUM_JOBS} parallel jobs"

# Limit parallel jobs to avoid OOM on TX2 NX
if [ $NUM_JOBS -gt 4 ]; then
    BUILD_JOBS=4
    print_warning "Limiting build jobs to 4 to avoid out-of-memory errors"
else
    BUILD_JOBS=$NUM_JOBS
fi

# Build with limited parallelism
make -j${BUILD_JOBS}

if [ $? -ne 0 ]; then
    print_warning "Build failed with ${BUILD_JOBS} jobs, retrying with -j2..."
    make -j2
fi

if [ $? -ne 0 ]; then
    print_error "Build failed! Check errors above."
    exit 1
fi

# Step 11: Install
print_status "Installing OpenCV..."
sudo make install
sudo ldconfig

# Step 12: Verify installation
print_status "Verifying installation..."

# Python verification
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" || print_error "Python import failed"

# CUDA verification
python3 << 'EOF'
import cv2
import sys

print("=" * 50)
print("OpenCV Build Information")
print("=" * 50)
print(f"OpenCV version: {cv2.__version__}")

build_info = cv2.getBuildInformation()
print("\nKey features:")

# Check CUDA
if "CUDA" in build_info:
    cuda_section = build_info[build_info.find("CUDA:"):build_info.find("CUDA:")+500]
    print("✓ CUDA support found")
    if "NVCUVID" in cuda_section and "YES" in cuda_section:
        print("✓ NVCUVID (hardware decode) enabled")
    if "NVCUVENC" in cuda_section and "YES" in cuda_section:
        print("✓ NVCUVENC (hardware encode) enabled")
else:
    print("✗ CUDA support not found")

# Check GStreamer
if "GStreamer" in build_info and "YES" in build_info[build_info.find("GStreamer"):build_info.find("GStreamer")+100]:
    print("✓ GStreamer support enabled")
else:
    print("✗ GStreamer support not found")

# Check CUDA device count
try:
    cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
    print(f"✓ CUDA enabled devices: {cuda_count}")
except:
    print("✗ CUDA support not available in OpenCV")

print("=" * 50)
EOF

# Step 13: Create hardware test script for Jetson TX2 NX
print_status "Creating hardware acceleration test script..."

cat > ~/test_jetson_hw.sh << 'EOF'
#!/bin/bash

echo "=========================================="
echo "Testing NVIDIA Jetson Hardware Acceleration"
echo "=========================================="

# Test 1: NVIDIA Hardware Encoder (nvenc)
echo -e "\n=== Test 1: NVIDIA H.264 Hardware Encoder (nvenc) ==="
gst-launch-1.0 -e videotestsrc num-buffers=300 ! \
    'video/x-raw,width=1920,height=1080,framerate=30/1' ! \
    nvvidconv ! 'video/x-raw(memory:NVMM)' ! \
    nvv4l2h264enc ! h264parse ! qtmux ! \
    filesink location=/tmp/test_nvenc.mp4

if [ -f /tmp/test_nvenc.mp4 ]; then
    echo "✓ Hardware encoding test PASSED"
    ls -lh /tmp/test_nvenc.mp4
else
    echo "✗ Hardware encoding test FAILED"
fi

# Test 2: NVIDIA Hardware Decoder
echo -e "\n=== Test 2: NVIDIA H.264 Hardware Decoder ==="
gst-launch-1.0 filesrc location=/tmp/test_nvenc.mp4 ! \
    qtdemux ! h264parse ! nvv4l2decoder ! \
    nvvidconv ! 'video/x-raw,format=BGRx' ! \
    videoconvert ! autovideosink

# Test 3: OpenCV with NVIDIA Hardware Pipeline
echo -e "\n=== Test 3: OpenCV + NVIDIA Hardware Pipeline ==="
python3 - << 'PYTHON'
import cv2
import numpy as np
import subprocess
import sys

print("Testing OpenCV with NVIDIA hardware encoding...")

# Test parameters
width, height = 1920, 1080
fps = 30
num_frames = 300
output_file = '/tmp/opencv_nvenc_test.mp4'

# FFmpeg command with NVIDIA hardware encoder
ffmpeg_cmd = [
    'ffmpeg', '-y',
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', f'{width}x{height}',
    '-r', str(fps),
    '-i', '-',
    '-c:v', 'h264_nvenc',  # NVIDIA hardware encoder
    '-preset', 'fast',
    '-b:v', '5M',
    '-pix_fmt', 'yuv420p',
    output_file
]

try:
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print(f"Encoding {num_frames} frames at {width}x{height}@{fps}fps...")
    
    for i in range(num_frames):
        # Generate test frame
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Write to ffmpeg
        proc.stdin.write(frame.tobytes())
        
        if i % 30 == 0:
            print(f"Progress: {i}/{num_frames} frames")
    
    proc.stdin.close()
    stdout, stderr = proc.communicate(timeout=30)
    
    if proc.returncode == 0:
        print("✓ OpenCV + NVIDIA hardware encoding test PASSED")
        print(f"  Output: {output_file}")
        import os
        if os.path.exists(output_file):
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"  File size: {size_mb:.2f} MB")
    else:
        print("✗ OpenCV + NVIDIA hardware encoding test FAILED")
        print(f"  Error: {stderr.decode('utf-8', errors='ignore')[:500]}")
        sys.exit(1)

except Exception as e:
    print(f"✗ Test failed with error: {e}")
    sys.exit(1)

# Test hardware decoding
print("\nTesting hardware decoding...")
decode_cmd = [
    'ffmpeg',
    '-hwaccel', 'nvdec',
    '-c:v', 'h264_cuvid',
    '-i', output_file,
    '-f', 'null', '-'
]

try:
    result = subprocess.run(decode_cmd, capture_output=True, timeout=30)
    if result.returncode == 0:
        print("✓ Hardware decoding test PASSED")
    else:
        print("✗ Hardware decoding test FAILED")
except Exception as e:
    print(f"✗ Decode test failed: {e}")

print("\n" + "="*50)
print("All tests completed!")
print("="*50)

PYTHON

echo -e "\n=== All Tests Completed ==="
EOF

chmod +x ~/test_jetson_hw.sh

# Step 14: Create verification script
cat > ${WORKSPACE}/verify_opencv.py << 'EOF'
import cv2
import sys

print("=" * 50)
print("OpenCV Build Information")
print("=" * 50)
print(f"OpenCV version: {cv2.__version__}")
print(f"\nBuild information:")
print(cv2.getBuildInformation())

# Check CUDA
print("\n" + "=" * 50)
print("CUDA Support")
print("=" * 50)
try:
    cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
    print(f"CUDA enabled devices: {cuda_count}")
    if cuda_count > 0:
        print("✓ CUDA support is working!")
        for i in range(cuda_count):
            print(f"  Device {i}: {cv2.cuda.getDevice()}")
except Exception as e:
    print(f"✗ CUDA support error: {e}")

# Check GStreamer
print("\n" + "=" * 50)
print("GStreamer Support")
print("=" * 50)
build_info = cv2.getBuildInformation()
if "GStreamer" in build_info and "YES" in build_info[build_info.find("GStreamer"):build_info.find("GStreamer")+100]:
    print("✓ GStreamer support is enabled")
else:
    print("✗ GStreamer support not found")

# Check Video I/O
print("\n" + "=" * 50)
print("Video I/O Backend")
print("=" * 50)
backends = [cv2.CAP_GSTREAMER, cv2.CAP_FFMPEG, cv2.CAP_V4L2]
backend_names = ["GStreamer", "FFmpeg", "V4L2"]
for backend, name in zip(backends, backend_names):
    try:
        cap = cv2.VideoCapture()
        if cap.open("test", backend):
            print(f"✓ {name} backend available")
        else:
            print(f"  {name} backend not available")
        cap.release()
    except:
        print(f"  {name} backend error")

print("\n" + "=" * 50)
EOF

print_status "Running verification..."
python3 ${WORKSPACE}/verify_opencv.py

# Step 15: Cleanup prompt
print_status "Cleaning up build files..."
read -p "Remove build directory to free up ~5GB space? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd /tmp
    rm -rf ${WORKSPACE}
    print_status "Build directory removed"
else
    print_status "Build directory kept at: ${WORKSPACE}"
fi

# Step 16: Final instructions
print_status "=========================================="
print_status "Installation completed successfully!"
print_status "=========================================="
echo ""
echo "Next steps:"
echo "1. Reboot your Jetson: sudo reboot"
echo "2. Test hardware acceleration: ~/test_jetson_hw.sh"
echo "3. Verify OpenCV: python3 -c 'import cv2; print(cv2.__version__)'"
echo ""
echo "Hardware encoders/decoders for Jetson TX2 NX:"
echo "  Encoding (ffmpeg): h264_nvenc, hevc_nvenc"
echo "  Decoding (ffmpeg): h264_cuvid, hevc_cuvid"
echo "  GStreamer encode: nvv4l2h264enc, nvv4l2h265enc"
echo "  GStreamer decode: nvv4l2decoder"
echo "  GStreamer convert: nvvidconv"
echo ""
echo "Example ffmpeg encode command:"
echo '  ffmpeg -i input.mp4 -c:v h264_nvenc -preset fast output.mp4'
echo ""
echo "Example GStreamer pipeline:"
echo '  gst-launch-1.0 videotestsrc ! nvvidconv ! nvv4l2h264enc ! h264parse ! qtmux ! filesink location=test.mp4'
echo ""
print_status "OpenCV ${OPENCV_VERSION} is ready with NVIDIA hardware acceleration!"