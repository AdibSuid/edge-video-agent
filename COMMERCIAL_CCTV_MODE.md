# Commercial CCTV Mode - Single Video Per Motion Event

## Overview
The system has been converted from chunked recording mode to commercial CCTV mode, where **each motion event is recorded as ONE continuous video file**, not split into multiple small chunks.

## What Changed

### Before (Chunked Mode)
- Used `splitmuxsink` with `max-size-time=5000000000ns` (5 seconds)
- Created new file every 5 seconds during motion
- Motion detection resulted in many small files (e.g., 00001.mp4, 00002.mp4, 00003.mp4, etc.)
- Had to manage "which chunks are complete" logic
- Skipped uploading most recent chunk to avoid corruption

### After (Commercial CCTV Mode)
- Uses `qtmux + filesink` for direct MP4 recording
- Records **one continuous file from motion start to motion end**
- Motion detection creates ONE video file with timestamp (e.g., `cam1_1234567890.mp4`)
- No chunk management needed
- Uploads complete file after motion ends

## Technical Changes

### 1. hardware_pipeline.py
**Changes:**
- `__init__()` now accepts `output_file` parameter
- Removed `splitmuxsink` (which creates chunks)
- Added `qtmux + filesink` for continuous recording
- Removed auto-reconnect `while self.running:` loop
- Pipeline records single file, then stops

**Pipeline Before:**
```python
'!', 'splitmuxsink',
f'location={output_dir}/{self.stream_id}_%05d.mp4',
f'max-size-time={chunk_duration_ns}',
```

**Pipeline After:**
```python
'!', 'qtmux',
'faststart=true',
'fragment-duration=1000',
'!', 'filesink',
f'location={self.output_file}',
'sync=false'
```

### 2. streamer.py
**Changes:**
- `_pipeline_manager_loop()` generates unique filename per motion event
- Passes `output_file` parameter to `HardwarePipeline()`
- Waits for pipeline to finish when motion ends
- Uploads single complete file
- Removed `_queue_new_chunks()` method (no longer needed)

**Workflow:**
1. Motion detected → Generate filename: `cam1_1234567890.mp4`
2. Start pipeline with specific output file
3. Pipeline records continuously while motion is active
4. Motion ends → Stop pipeline
5. Wait 2 seconds for GStreamer to finalize file
6. Upload the complete motion event file

## Benefits

### Commercial CCTV Behavior
✅ **One video per motion event** (like Hikvision, Dahua, etc.)
✅ **Cleaner file management** - no need to track chunks
✅ **Simpler upload logic** - upload one complete file
✅ **Better user experience** - each file = one motion event
✅ **Easier playback** - watch entire event in one video

### Hardware Acceleration
✅ **NVDEC** for RTSP stream decoding
✅ **NVENC** for H.264 encoding
✅ **Same hardware optimization** as before
✅ **No performance loss** - still using GStreamer hardware pipeline

## File Naming Convention
```
{stream_id}_{unix_timestamp}.mp4
```

Examples:
- `cam1_1735712345.mp4` - Camera 1 motion event at timestamp 1735712345
- `cam2_1735712456.mp4` - Camera 2 motion event at timestamp 1735712456
- `cam3_1735712567.mp4` - Camera 3 motion event at timestamp 1735712567

## Comparison with Old Version (562c924)

| Feature | Old Version | Current System |
|---------|-------------|----------------|
| Motion Detection | ✅ Yes | ✅ Yes |
| One File Per Event | ✅ Yes | ✅ Yes |
| Hardware Encoding | ❌ No (CPU) | ✅ Yes (NVENC) |
| Hardware Decoding | ❌ No (CPU) | ✅ Yes (NVDEC) |
| GStreamer Pipeline | ❌ No (OpenCV) | ✅ Yes |
| Performance | Good | **Excellent** |

## Testing

### How to Test
1. Start the system: `python app.py`
2. Trigger motion on a camera
3. Check logs: `tail -f logs/cam1.log`
4. Check output: `ls -lh tmp/chunks/`

### Expected Behavior
✅ Motion detected → Log shows: "🎬 Motion detected! Recording to: tmp/chunks/cam1_1234567890.mp4"
✅ During motion → Single file size increases continuously
✅ Motion ended → Log shows: "⏹ Motion ended. Stopping pipeline..."
✅ After motion → Log shows: "✓ Motion event saved: tmp/chunks/cam1_1234567890.mp4 (2.5 MB)"
✅ Upload → File queued and uploaded to cloud

### NOT Expected (Old Chunked Behavior)
❌ Multiple files created every 5 seconds
❌ Files named with sequence numbers (00001.mp4, 00002.mp4, etc.)
❌ Batch uploads of multiple chunks
❌ Skipping most recent chunk logic

## Troubleshooting

### If Files Are Still Split
Check `config.yaml`:
```yaml
use_hardware_pipeline: true  # Must be true
chunking_enabled: true       # Must be true for recording
```

### If Files Are Too Small
- Check motion cooldown setting (default: 3 seconds)
- Motion must be active for at least a few seconds to generate meaningful video
- Adjust `motion_cooldown` if needed

### If Upload Fails
- Check cloud credentials in `config.yaml`
- Check logs: `tail -f logs/hw_pipeline_cam1.log`
- Verify file exists and has reasonable size (> 100KB)

## Summary
✅ **One continuous video per motion event** - just like commercial CCTV
✅ **Hardware acceleration maintained** - NVENC/NVDEC active
✅ **Same behavior as version 562c924** - but with hardware encoding
✅ **Cleaner, simpler code** - no chunk management complexity
✅ **Better user experience** - each file represents one motion event

The system now behaves exactly like commercial CCTV systems while utilizing Jetson TX2 NX hardware acceleration for maximum performance! 🎥
