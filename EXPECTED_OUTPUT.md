# Expected Output: Hardware Acceleration Test

## Command
```bash
gst-launch-1.0 videotestsrc num-buffers=30 ! nvv4l2h264enc ! fakesink
```

## ✅ SUCCESS Output

If hardware acceleration is working, you should see:

```
Setting pipeline to PAUSED ...
Pipeline is PREROLLING ...
NvMMLiteOpen : Block : BlockType = 261
NVMEDIA: Reading vendor.tegra.display-size : status: 6
NvMMLiteBlockCreate : Block : BlockType = 261
Allocating new output: 1920x1080 (x 6), ThumbnailMode = 0
Pipeline is PREROLLED ...
Setting pipeline to PLAYING ...
New clock: GstSystemClock
Got EOS from element "pipeline0".
Execution ended after 0:00:01.234567890
Setting pipeline to NULL ...
Freeing pipeline ...
```

**Key indicators of success**:
- ✅ No error messages
- ✅ "NvMMLite" messages (NVIDIA Media Lite API)
- ✅ "Pipeline is PLAYING"
- ✅ "Got EOS" (End of Stream)
- ✅ Clean exit with "Freeing pipeline"

## ❌ FAILURE: Missing Plugin

If `nvv4l2h264enc` is not installed:

```
WARNING: erroneous pipeline: no element "nvv4l2h264enc"
```

**What this means**: GStreamer plugin not found
**Fix**:
```bash
sudo apt-get install gstreamer1.0-plugins-bad
```

## ❌ FAILURE: Permission Denied

If you don't have permission to access hardware:

```
Setting pipeline to PAUSED ...
Pipeline is PREROLLING ...
ERROR: from element /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0: Could not open resource for writing.
Additional debug info:
gstnvv4l2h264enc.c(XXX): gst_nvv4l2h264enc_set_format (): /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0:
Could not open device '/dev/nvhost-msenc' for writing
ERROR: pipeline doesn't want to preroll.
Setting pipeline to NULL ...
Freeing pipeline ...
```

**What this means**: Permission denied on `/dev/nvhost-msenc` or similar device
**Fix**:
```bash
# Add user to video group
sudo usermod -a -G video $USER

# Logout and login again (critical!)
```

## ❌ FAILURE: Device Busy

If another process is using the encoder:

```
ERROR: from element /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0: Internal data stream error.
Additional debug info:
gstbasesrc.c(XXX): gst_base_src_loop (): /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0:
streaming stopped, reason not-negotiated (-4)
```

**What this means**: Hardware encoder in use by another app, or configuration issue
**Fix**:
- Stop other applications using the encoder
- Reboot if necessary

## ❌ FAILURE: Wrong JetPack Version / Missing Driver

If NVIDIA drivers are missing:

```
ERROR: from element /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0: Could not initialize supporting library.
Additional debug info:
gstnvv4l2h264enc.c(XXX): gst_nvv4l2h264enc_init (): /GstPipeline:pipeline0/Gstnvv4l2h264enc:nvv4l2h264enc0:
Cannot initialize encoder
```

**What this means**: NVIDIA multimedia drivers not loaded or incompatible
**Check**:
```bash
# Verify JetPack version
cat /etc/nv_tegra_release

# Check if nvhost modules loaded
lsmod | grep nvhost
```

## 🔍 Detailed Success Output Example

Here's what a complete successful run looks like:

```
jetson@jetson-desktop:~$ gst-launch-1.0 videotestsrc num-buffers=30 ! nvv4l2h264enc ! fakesink
Setting pipeline to PAUSED ...
Pipeline is PREROLLING ...
NvMMLiteOpen : Block : BlockType = 261
NVMEDIA: Reading vendor.tegra.display-size : status: 6
NvMMLiteBlockCreate : Block : BlockType = 261
H264: Profile = 66, Level = 0
Allocating new output: 320x240 (x 6), ThumbnailMode = 0
Pipeline is PREROLLED ...
Setting pipeline to PLAYING ...
New clock: GstSystemClock
Got EOS from element "pipeline0".
Execution ended after 0:00:01.012345678
Setting pipeline to NULL ...
Freeing pipeline ...
```

**What each part means**:
- `NvMMLiteOpen`: Opening NVIDIA Media Lite library ✅
- `BlockType = 261`: Hardware encoder block initialized ✅
- `H264: Profile = 66`: H.264 Baseline profile ✅
- `Allocating new output`: Hardware buffer allocation ✅
- `Got EOS`: All 30 frames processed successfully ✅

## 📊 Performance Indicators

In the success output, look at the execution time:
```
Execution ended after 0:00:01.012345678
```

For 30 frames:
- **~1 second = Good** (hardware accelerated)
- **3+ seconds = Bad** (might be falling back to software)

## 🧪 More Test Commands

### Test with file output (more reliable)
```bash
gst-launch-1.0 videotestsrc num-buffers=30 ! \
    nvv4l2h264enc ! \
    h264parse ! qtmux ! \
    filesink location=/tmp/test.mp4

# Check if file was created
ls -lh /tmp/test.mp4
# Should show a file around 100-500KB
```

### Test hardware decoder
```bash
gst-launch-1.0 videotestsrc num-buffers=30 ! \
    x264enc ! h264parse ! \
    nvv4l2decoder ! \
    fakesink
```

### Test full encode-decode pipeline
```bash
gst-launch-1.0 videotestsrc num-buffers=30 ! \
    nvv4l2h264enc ! h264parse ! \
    nvv4l2decoder ! \
    videoconvert ! autovideosink
```

## 🔍 Debugging Tips

If you get errors, run with debug output:

```bash
# Full debug
GST_DEBUG=3 gst-launch-1.0 videotestsrc num-buffers=30 ! nvv4l2h264enc ! fakesink

# Focus on nvv4l2 messages only
GST_DEBUG=nvv4l2*:5 gst-launch-1.0 videotestsrc num-buffers=30 ! nvv4l2h264enc ! fakesink
```

## 📋 Quick Checklist

After running the command, check:

| Check | Command | Expected |
|-------|---------|----------|
| No errors | (look at output) | No "ERROR:" or "WARNING:" |
| NvMMLite loaded | `grep NvMM` | Should see "NvMMLiteOpen" |
| Got EOS | `grep EOS` | Should see "Got EOS" |
| Clean exit | (look at end) | "Freeing pipeline" |
| Fast execution | (check time) | < 2 seconds for 30 frames |

## ✅ What Success Looks Like

**Minimal success output** (some verbosity may vary):
```
Setting pipeline to PAUSED ...
Pipeline is PREROLLING ...
Pipeline is PREROLLED ...
Setting pipeline to PLAYING ...
New clock: GstSystemClock
Got EOS from element "pipeline0".
Execution ended after 0:00:01.XXX
Setting pipeline to NULL ...
Freeing pipeline ...
```

If you see this with **no ERROR messages**, hardware encoding is working! 🎉

## ⚠️ What Failure Looks Like

Any of these = problem:
- ❌ `ERROR:` in output
- ❌ `WARNING: erroneous pipeline`
- ❌ `Could not open resource`
- ❌ `Permission denied`
- ❌ `no element "nvv4l2h264enc"`
- ❌ Pipeline hangs (doesn't complete)
- ❌ Takes > 5 seconds for 30 frames

## 🎯 Next Steps Based on Output

**If success**: Your hardware acceleration works! Run your app.

**If "no element"**: Install gstreamer1.0-plugins-bad

**If "permission denied"**: Add to video group, logout/login

**If other errors**: Run `./test_hardware_acceleration.sh` for diagnosis

---

## Compare Your Output

**Run the command and compare with examples above.**

If your output doesn't match the success pattern, share what you see and I can tell you exactly what's wrong!
