# Quick Start: Enable Hardware Acceleration on TX2 NX

**For**: Jetson TX2 NX with JetPack 4.5.1
**Goal**: Full hardware acceleration (decode + encode)
**Time**: ~2.5 hours

---

## TL;DR - Three Commands

```bash
# On your TX2 NX:

# 1. Run compatibility check (2 minutes)
./test_tx2_compatibility.sh

# 2. Rebuild OpenCV with GStreamer (2 hours - automated)
chmod +x rebuild_opencv_tx2.sh
./rebuild_opencv_tx2.sh

# 3. Update code (see below)
```

---

## Step-by-Step (Minimal Version)

### 1️⃣ Check Current Status (2 min)

```bash
cd /path/to/edge-video-agent
chmod +x test_tx2_compatibility.sh
./test_tx2_compatibility.sh
```

Look for:
- ✗ OpenCV GStreamer Support: NO ← This is what we'll fix
- ✓ nvv4l2decoder: Available ← Should already be YES
- ✓ nvv4l2h264enc: Available ← Should already be YES

### 2️⃣ Rebuild OpenCV (2 hours - mostly waiting)

```bash
# Make script executable
chmod +x rebuild_opencv_tx2.sh

# Run automated build
./rebuild_opencv_tx2.sh
```

**What this does:**
- Installs dependencies
- Downloads OpenCV 4.5.5
- Builds with GStreamer + CUDA support
- Installs to /usr/local

**Go get coffee** ☕ - this takes ~2 hours.

**After it finishes**, verify:
```bash
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep GStreamer
# Should show: GStreamer: YES
```

### 3️⃣ Update Your Code (15 min)

Open `streamer.py` and find the `_encode_chunk_hardware` method (around line 178).

**Replace the entire method** with this:

```python
def _encode_chunk_hardware(self, frames, out_path, fps):
    """Encode using GStreamer nvv4l2h264enc (community standard)."""
    try:
        import cv2
        import subprocess

        if not frames:
            return False

        h, w = frames[0].shape[:2]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if on Jetson
        is_jetson = os.path.exists('/etc/nv_tegra_release')
        if not is_jetson:
            return False

        # GStreamer command for hardware encoding
        gst_cmd = [
            'gst-launch-1.0', '-e',
            'fdsrc', '!',
            f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
            'videoconvert', '!',
            'video/x-raw,format=I420', '!',
            'nvv4l2h264enc',
            'maxperf-enable=true',
            'bitrate=2000000',
            'preset-level=1',
            'insert-sps-pps=true',
            'idrinterval=30', '!',
            'h264parse', '!',
            'qtmux', '!',
            f'filesink location={out_path}'
        ]

        self.logger.info(f"Encoding with nvv4l2h264enc: {w}x{h} @ {fps}fps")

        # Run GStreamer
        proc = subprocess.Popen(gst_cmd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Write frames
        for frame in frames:
            try:
                proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, IOError):
                break

        proc.stdin.close()
        proc.wait(timeout=10)

        success = proc.returncode == 0 and out_path.exists()
        if success:
            self.logger.info(f"✓ Hardware encoding succeeded: {out_path.name}")
        else:
            self.logger.warning("✗ Hardware encoding failed")

        return success

    except Exception as e:
        self.logger.error(f"Encoding error: {e}")
        return False
```

Save the file.

### 4️⃣ Test Everything (5 min)

```bash
# Test standalone encoding
python3 << 'EOF'
import cv2, numpy as np, subprocess
from pathlib import Path

frames = [np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8) for _ in range(60)]
h, w, fps = 1080, 1920, 2
out = Path('/tmp/test.mp4')

gst_cmd = ['gst-launch-1.0', '-e', 'fdsrc', '!',
    f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
    'videoconvert', '!', 'nvv4l2h264enc', 'bitrate=2000000', '!',
    'h264parse', '!', 'qtmux', '!', f'filesink location={out}']

proc = subprocess.Popen(gst_cmd, stdin=subprocess.PIPE)
for f in frames: proc.stdin.write(f.tobytes())
proc.stdin.close()
proc.wait()

print(f"✓ Test passed: {out} ({out.stat().st_size} bytes)" if out.exists() else "✗ Test failed")
EOF

# Run your application
python3 app.py
```

Check logs for:
```
✓ Hardware encoding succeeded
```

---

## Verification Checklist

After completing all steps, verify:

- [ ] `./test_tx2_compatibility.sh` shows all green ✓
- [ ] OpenCV has GStreamer support: YES
- [ ] Application logs show "nvv4l2h264enc"
- [ ] CPU usage < 30% during operation
- [ ] Video chunks are created successfully

---

## Troubleshooting

### Build fails with "No space left"
```bash
# Clean up space
sudo apt-get clean
sudo apt-get autoremove
df -h  # Need at least 5GB free

# Try with fewer cores
# Edit rebuild_opencv_tx2.sh, change: make -j4 → make -j2
```

### OpenCV shows "GStreamer: NO" after build
```bash
# Check if GStreamer dev packages exist
dpkg -l | grep gstreamer1.0-dev

# Reinstall if missing
sudo apt-get install --reinstall libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev

# Clean build and retry
cd ~/opencv_build/opencv-4.5.5/build
rm -rf *
./rebuild_opencv_tx2.sh  # Starts from cmake step
```

### Application still uses software encoding
```bash
# Check code update
grep "nvv4l2h264enc" streamer.py
# Should find it in _encode_chunk_hardware method

# Check logs
tail -f logs/*.log
# Look for "Encoding with nvv4l2h264enc"
```

---

## Performance Expected

**Before (Software):**
- CPU: 80-90%
- Encode: 5-10 fps @ 1080p
- Decode: 10-15 fps @ 1080p

**After (Hardware):**
- CPU: 15-30%
- Encode: 25-30 fps @ 1080p
- Decode: 30 fps @ 1080p

Monitor with:
```bash
tegrastats  # GPU and hardware encoder usage
htop        # CPU usage
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `STEP_BY_STEP_FIX.md` | Detailed guide (you are here) |
| `QUICK_START.md` | Quick reference (this file) |
| `rebuild_opencv_tx2.sh` | Automated OpenCV build |
| `test_tx2_compatibility.sh` | System compatibility check |
| `COMMUNITY_STANDARD_FIX.md` | GStreamer implementation details |

---

## Need More Help?

**Detailed guide**: See `STEP_BY_STEP_FIX.md`
**Technical details**: See `COMMUNITY_STANDARD_FIX.md`
**Current code analysis**: See `TX2_JP4_COMPATIBILITY_ANALYSIS.md`

---

## Summary

1. ✅ Run `./rebuild_opencv_tx2.sh` (wait 2 hours)
2. ✅ Update `_encode_chunk_hardware` in `streamer.py`
3. ✅ Test and enjoy 3-5x performance boost! 🚀
