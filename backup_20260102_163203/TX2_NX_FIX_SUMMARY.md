# Fixing Hardware Encode/Decode on Jetson TX2 NX (JetPack 4)

## Problem

Your current code is designed for **JetPack 5** (Orin series) but you're running on **TX2 NX with JetPack 4**, which uses different hardware acceleration APIs.

| Feature | JetPack 4 (TX2 NX) | JetPack 5 (Orin) | Current Code |
|---------|-------------------|------------------|--------------|
| **Decode API** | OpenMAX (OMX) | V4L2 | V4L2 ✗ |
| **GStreamer Decoder** | `omxh264dec` | `nvv4l2decoder` | nvv4l2decoder ✗ |
| **FFmpeg Encoder** | `h264_nvenc` or `h264_omx` | `h264_nvenc` | Tries NVENC (may work) |

## Solution Overview

1. **Detect JetPack version** at runtime
2. **Use correct GStreamer elements** (omxh264dec for JP4, nvv4l2decoder for JP5)
3. **Use correct FFmpeg encoders** (h264_omx or h264_nvenc for JP4)
4. **Install required dependencies** on TX2 NX

## Step-by-Step Fix

### Step 1: Install Dependencies on TX2 NX

Run these commands on your TX2 NX:

```bash
# Make setup script executable
chmod +x setup_tx2_nx_jp4.sh

# Run setup (installs GStreamer, FFmpeg, etc.)
./setup_tx2_nx_jp4.sh
```

This installs:
- GStreamer 1.0 with OMX plugins
- FFmpeg with hardware encoder support
- Required NVIDIA libraries

### Step 2: Verify Hardware Support

```bash
# Run diagnostic script
chmod +x check_jetpack4_hardware.sh
./check_jetpack4_hardware.sh
```

You should see:
- ✓ `omxh264dec` available (for decode)
- ✓ `h264_omx` or `h264_nvenc` available (for encode)
- OpenCV with GStreamer support: YES

### Step 3: Test JetPack Detection

```bash
python3 jetpack_utils.py
```

Expected output:
```
JetPack Version: 4.6
Hardware Configuration:
  API Type: omx
  GStreamer Decoder: omxh264dec
  FFmpeg Encoder: h264_nvenc
  FFmpeg Encoder Fallback: h264_omx
```

### Step 4: Update streamer.py

Apply the changes from `streamer_jetpack4_patch.py` to your `streamer.py`:

**Change 1** - Add import (after line 20):
```python
from jetpack_utils import get_hardware_config, check_encoder_available, check_gstreamer_element
```

**Change 2** - Detect hardware in `__init__` (after line 77):
```python
# Detect JetPack version and hardware capabilities
self.hw_config = get_hardware_config()
self.logger.info(f"Detected hardware config: {self.hw_config['api_type']} "
                f"(JetPack {self.hw_config['jetpack_major']}.{self.hw_config['jetpack_minor']})")
```

**Change 3** - Update `_capture_loop_hw_decode` method (line 763):
- Use `self.hw_config['gstreamer_decoder']` instead of hardcoded `nvv4l2decoder`
- Build GStreamer pipeline based on API type

**Change 4** - Update `_encode_chunk_hardware` method (line 213):
- Use `self.hw_config['ffmpeg_encoder']` instead of hardcoded encoder
- Try primary encoder, then fallback

See `streamer_jetpack4_patch.py` for complete code.

### Step 5: Test Hardware Decode

Test GStreamer pipeline manually:

```bash
# Replace with your RTSP URL
gst-launch-1.0 rtspsrc location=rtsp://admin:password@192.168.0.14:554/stream ! \
    rtph264depay ! h264parse ! omxh264dec ! videoconvert ! autovideosink
```

If this works, hardware decode is ready!

### Step 6: Test Hardware Encode

Test FFmpeg encoding:

```bash
# Test with NVENC (if available)
ffmpeg -f lavfi -i testsrc=duration=5:size=1920x1080:rate=30 \
    -c:v h264_nvenc -preset fast test_nvenc.mp4

# Test with OMX (fallback)
ffmpeg -f lavfi -i testsrc=duration=5:size=1920x1080:rate=30 \
    -c:v h264_omx -b:v 2M test_omx.mp4
```

### Step 7: Update Configuration

Ensure your `config.yaml` has:

```yaml
use_hardware_decode: true
use_hardware_encode: true
motion_detection_scale: 0.25
motion_frame_skip: 2
chunk_fps: 2
encoding_preset: ultrafast
```

### Step 8: Run Your Application

```bash
python3 app.py
```

Check logs for:
- `Detected hardware config: omx (JetPack 4.x)`
- `Using JetPack 4 OMX pipeline: omxh264dec`
- `✓ Hardware encoding succeeded with h264_omx` (or h264_nvenc)

## Troubleshooting

### Issue: OpenCV doesn't have GStreamer support

**Symptom**: Hardware decode fails, logs show "Failed to open GStreamer pipeline"

**Fix**: Rebuild OpenCV with GStreamer enabled. See detailed instructions in `JETPACK4_TX2_SETUP.md` section "3. OpenCV with GStreamer Support"

This takes 1-2 hours but is necessary for hardware decode.

### Issue: omxh264dec not found

**Symptom**: `gst-inspect-1.0 omxh264dec` fails

**Fix**:
```bash
sudo apt-get install gstreamer1.0-omx-generic
```

### Issue: h264_nvenc not found, only h264_omx available

**Symptom**: FFmpeg shows `h264_omx` but not `h264_nvenc`

**Fix**: This is normal for TX2 NX. The code will automatically use `h264_omx` as fallback. If you want NVENC, you need to build FFmpeg from source (see `JETPACK4_TX2_SETUP.md`).

### Issue: Library errors like "libnvbufsurface.so not found"

**Fix**:
```bash
export LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/tegra:$LD_LIBRARY_PATH
# Add to ~/.bashrc to make permanent
```

### Issue: Still using software decode/encode

**Check**:
1. Run `python3 jetpack_utils.py` - verify detection works
2. Check logs in `logs/<stream_id>.log` for error messages
3. Verify `config.yaml` has `use_hardware_decode: true` and `use_hardware_encode: true`
4. Test GStreamer and FFmpeg commands manually (see Step 5 and 6)

## Performance Expectations

**TX2 NX Capabilities:**
- Video Encode: 1x 4K@30fps or 2x 1080p@60fps
- Video Decode: 1x 4K@60fps or 4x 1080p@30fps
- Recommended: 2-4 concurrent camera streams

**Typical Results:**
- Software encode: 5-10 fps @ 1080p (CPU bound)
- Hardware encode: 25-30 fps @ 1080p (offloaded to dedicated encoder)
- Hardware decode: Reduces CPU usage by 50-70%

## Files Created

1. **check_jetpack4_hardware.sh** - Diagnostic script to check hardware support
2. **JETPACK4_TX2_SETUP.md** - Detailed setup guide with build instructions
3. **jetpack_utils.py** - JetPack detection and hardware config utility
4. **streamer_jetpack4_patch.py** - Code changes needed for streamer.py
5. **setup_tx2_nx_jp4.sh** - Automated dependency installation script
6. **TX2_NX_FIX_SUMMARY.md** - This file

## Quick Start (TL;DR)

```bash
# On TX2 NX:
chmod +x setup_tx2_nx_jp4.sh check_jetpack4_hardware.sh
./setup_tx2_nx_jp4.sh
./check_jetpack4_hardware.sh
python3 jetpack_utils.py

# Update streamer.py with changes from streamer_jetpack4_patch.py
# Then run your app
python3 app.py
```

## Need Help?

1. Check `JETPACK4_TX2_SETUP.md` for detailed requirements
2. Run diagnostics: `./check_jetpack4_hardware.sh`
3. Check application logs: `tail -f logs/<stream_id>.log`
4. Test components individually (GStreamer, FFmpeg) before running full app
