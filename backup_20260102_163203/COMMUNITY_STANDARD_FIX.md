# Community Standard Implementation for Jetson TX2 NX (JetPack 4)

## What I Got Wrong

My previous recommendations had **critical errors**:

1. ❌ Recommended **OMX plugins** for JetPack 4 → Should use **V4L2** (OMX deprecated since JP 4.2)
2. ❌ Used **FFmpeg** for encoding → Should use **GStreamer** (NVIDIA standard)
3. ❌ Suggested JP4 and JP5 use different APIs → Both use **V4L2** (unified API)

## Community Standard (from NVIDIA docs + jetson-utils)

### Both JetPack 4 and 5 Use the Same V4L2 Plugins:

| Component | JetPack 4 (TX2 NX) | JetPack 5 (Orin) |
|-----------|-------------------|------------------|
| **Decoder** | `nvv4l2decoder` | `nvv4l2decoder` |
| **Encoder** | `nvv4l2h264enc` | `nvv4l2h264enc` |
| **API** | V4L2 | V4L2 |
| **Tool** | GStreamer | GStreamer |

**Key Insight**: JetPack 4.2+ and JetPack 5 use the **same** V4L2 plugins!

## Correct Hardware Detection

```python
def get_hardware_config():
    """Get hardware config - V4L2 is standard for all modern JetPack versions."""
    jp_major, jp_minor = get_jetpack_version()

    # JetPack 4.2+ and 5.x all use V4L2
    if jp_major >= 4:
        return {
            'jetpack_version': (jp_major, jp_minor),
            'gstreamer_decoder': 'nvv4l2decoder',
            'gstreamer_encoder': 'nvv4l2h264enc',
            'api_type': 'v4l2',
            'use_gstreamer': True,  # NOT FFmpeg
        }
    else:
        # JetPack 3.x or non-Jetson
        return {
            'jetpack_version': (None, None),
            'gstreamer_decoder': None,
            'gstreamer_encoder': None,
            'api_type': 'software',
            'use_gstreamer': False,
        }
```

## Correct Decoding (GStreamer)

**Your current code is already correct:**

```python
def _capture_loop_hw_decode(self):
    """Hardware decode via GStreamer (community standard)."""
    gst_pipeline = (
        f"rtspsrc location={self.rtsp_url} latency=0 ! "
        "rtph264depay ! h264parse ! "
        "nvv4l2decoder ! "  # Works on both JP4 and JP5
        "nvvidconv ! "
        "video/x-raw,format=BGRx ! videoconvert ! "
        "video/x-raw,format=BGR ! appsink"
    )

    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    # ... rest of implementation
```

✅ This is the community standard method.

## Correct Encoding (GStreamer, NOT FFmpeg)

**Replace your FFmpeg encoding with GStreamer:**

```python
def _encode_chunk_hardware(self, frames, out_path, fps):
    """
    Encode using GStreamer with nvv4l2h264enc (community standard).

    This is the NVIDIA-recommended approach used by jetson-utils.
    """
    try:
        import cv2
        if not frames:
            return False

        h, w = frames[0].shape[:2]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # GStreamer pipeline for hardware encoding
        # This is the community standard approach
        gst_pipeline = (
            f"appsrc ! "
            f"video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1 ! "
            "videoconvert ! "
            "video/x-raw,format=I420 ! "
            "nvv4l2h264enc "
            "maxperf-enable=true "  # Enable max performance mode
            "bitrate=2000000 "       # 2 Mbps
            "preset-level=1 "        # UltraFastPreset (0=slow, 1=medium, 2=fast, 3=ultrafast)
            "insert-sps-pps=true "   # Insert SPS/PPS at every IDR
            "idrinterval=30 ! "      # IDR interval
            "h264parse ! "
            "qtmux ! "
            f"filesink location={out_path}"
        )

        self.logger.info(f"Encoding with nvv4l2h264enc (GStreamer): {w}x{h} @ {fps}fps")

        # Create GStreamer VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'H264')
        writer = cv2.VideoWriter(
            gst_pipeline,
            cv2.CAP_GSTREAMER,
            fourcc,
            fps,
            (w, h),
            True
        )

        if not writer.isOpened():
            self.logger.error("Failed to open GStreamer encoder")
            return False

        # Write frames
        frames_written = 0
        for frame in frames:
            writer.write(frame)
            frames_written += 1

        writer.release()

        success = out_path.exists() and out_path.stat().st_size > 0

        if success:
            self.logger.info(f"✓ GStreamer encoding succeeded: {out_path.name}")
        else:
            self.logger.error("✗ GStreamer encoding failed")

        return success

    except Exception as e:
        self.logger.error(f"GStreamer encoding error: {e}")
        return False
```

## Alternative: Use subprocess with GStreamer (More Control)

If OpenCV's GStreamer integration doesn't work well, use subprocess:

```python
def _encode_chunk_hardware_gst_subprocess(self, frames, out_path, fps):
    """
    Encode using GStreamer subprocess (more reliable than OpenCV integration).
    Based on jetson-utils and NVIDIA examples.
    """
    try:
        import subprocess
        import numpy as np

        if not frames:
            return False

        h, w = frames[0].shape[:2]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # GStreamer command (industry standard)
        gst_cmd = [
            'gst-launch-1.0',
            '-e',  # Send EOS on interrupt
            'fdsrc', '!',
            f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
            'videoconvert', '!',
            'video/x-raw,format=I420', '!',
            'nvv4l2h264enc',
            'maxperf-enable=true',
            'bitrate=2000000',
            'preset-level=1',  # UltraFastPreset
            'insert-sps-pps=true',
            'idrinterval=30', '!',
            'h264parse', '!',
            'qtmux', '!',
            f'filesink location={out_path}'
        ]

        self.logger.info(f"Encoding with GStreamer pipeline: {w}x{h} @ {fps}fps")

        proc = subprocess.Popen(
            gst_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Write frames to GStreamer stdin
        frames_written = 0
        for frame in frames:
            try:
                proc.stdin.write(frame.tobytes())
                frames_written += 1
            except (BrokenPipeError, IOError):
                break

        # Close and wait
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        success = proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0

        if success:
            self.logger.info(f"✓ GStreamer encoding succeeded: {frames_written} frames")
        else:
            stderr = proc.stderr.read().decode('utf-8', errors='ignore')[:500]
            self.logger.error(f"✗ GStreamer encoding failed: {stderr}")

        return success

    except Exception as e:
        self.logger.error(f"GStreamer subprocess error: {e}")
        return False
```

## Performance Optimization (from Community Research)

Based on RidgeRun's performance testing, use these GStreamer properties:

```bash
nvv4l2h264enc properties:
  maxperf-enable=true        # Enable max performance (lowest latency)
  preset-level=1             # 0=Slow, 1=Medium, 2=Fast, 3=UltraFast
  bitrate=2000000            # Target bitrate (2 Mbps)
  peak-bitrate=3000000       # Peak bitrate for VBR
  control-rate=1             # 0=variable, 1=constant
  profile=0                  # 0=Baseline, 1=Main, 2=High
  insert-sps-pps=true        # Insert SPS/PPS at every IDR
  insert-vui=true            # Insert VUI for timing info
  idrinterval=30             # IDR frame interval
```

## Why GStreamer, Not FFmpeg?

According to research and NVIDIA documentation:

1. **Official Support**: NVIDIA provides and maintains GStreamer plugins
2. **Better Performance**: V4L2 encoders with maxperf-enable have lowest latency
3. **Zero-Copy**: GStreamer uses NVMM (NVIDIA Memory Management) for zero-copy
4. **Proven**: Used by jetson-utils, jetson-inference, and all NVIDIA examples
5. **FFmpeg Not Supported**: Requires unofficial community patches

## Requirements for TX2 NX (JetPack 4)

```bash
# Install GStreamer and V4L2 plugins
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    gstreamer1.0-nvv4l2 \
    libgstreamer1.0-dev

# Verify V4L2 plugins (NOT OMX)
gst-inspect-1.0 nvv4l2decoder
gst-inspect-1.0 nvv4l2h264enc

# OpenCV with GStreamer support
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer
# Should show: GStreamer: YES
```

## Testing Hardware Encode (Community Method)

```bash
# Test GStreamer encoding directly
gst-launch-1.0 -e \
    videotestsrc num-buffers=300 ! \
    'video/x-raw,width=1920,height=1080,framerate=30/1' ! \
    nvv4l2h264enc maxperf-enable=true bitrate=2000000 ! \
    h264parse ! qtmux ! filesink location=test.mp4

# Test decoding
gst-launch-1.0 \
    filesrc location=test.mp4 ! \
    qtdemux ! h264parse ! nvv4l2decoder ! \
    videoconvert ! autovideosink
```

## Summary: What to Change

### ❌ Remove from Your Code:
1. All FFmpeg encoding logic in `_encode_chunk_hardware`
2. OMX plugin references (`omxh264dec`, `omxh264enc`)
3. FFmpeg encoder selection (h264_nvenc, h264_omx)

### ✅ Use Instead:
1. GStreamer for both decode AND encode
2. V4L2 plugins for JetPack 4 and 5 (`nvv4l2decoder`, `nvv4l2h264enc`)
3. Follow jetson-utils pattern

### Key Takeaway:

**Your current decode is correct (GStreamer + nvv4l2decoder).**
**Your current encode is wrong (FFmpeg subprocess).**
**Switch encoding to GStreamer pipeline = Community standard.**

## References

- [NVIDIA L4T Accelerated GStreamer Guide](https://docs.nvidia.com/jetson/archives/l4t-archived/l4t-3251/Tegra%20Linux%20Driver%20Package%20Development%20Guide/accelerated_gstreamer.html)
- [jetson-utils (NVIDIA's example code)](https://github.com/dusty-nv/jetson-utils)
- [RidgeRun GStreamer Performance Guide](https://developer.ridgerun.com/wiki/index.php/GStreamer_Encoding_Latency_in_NVIDIA_Jetson_Platforms)
