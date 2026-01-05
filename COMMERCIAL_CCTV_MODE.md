# Fixed-Duration Chunk Mode - Configurable Video Chunks

## Overview
The system records motion events as **fixed-duration video chunks** based on the `chunk_duration` setting (5-15 seconds). Each motion event may result in multiple chunk files depending on how long motion lasts.

## What This Means

### Chunk Duration Behavior
- **chunk_duration: 8 seconds**
  - Motion for 5 seconds → Creates 1 chunk of 8 seconds (includes padding after motion ends)
  - Motion for 20 seconds → Creates 3 chunks: 8s, 8s, 4s
  - Motion for 40 seconds → Creates 5 chunks: 8s, 8s, 8s, 8s, 8s

### Key Features
- ✅ **Fixed chunk size**: All chunks are the configured duration (except the last chunk)
- ✅ **Consistent file sizes**: Easy to manage and predict storage usage
- ✅ **Easy to browse**: Shorter files are easier to scrub through
- ✅ **Hardware accelerated**: Still uses NVENC/NVDEC for encoding/decoding

## Technical Changes

### 1. hardware_pipeline.py
**Uses `splitmuxsink` for time-based splitting:**

```python
'!', 'splitmuxsink',
f'location={output_pattern}',
f'max-size-time={chunk_duration_ns}',  # Split every N seconds
'muxer-factory=qtmux',
'async-finalize=true'
```

### 2. streamer.py
**Uploads all chunks from a recording session:**
- Tracks when recording session starts
- After motion ends + retrigger time, finds all chunks from that session
- Uploads each chunk individually

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
