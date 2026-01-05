# Fixed-Duration Chunking Implementation

## Date: January 5, 2026

## Summary
Implemented **fixed-duration video chunking** where video chunks are created based on the `chunk_duration` setting (5-15 seconds), **regardless of actual motion duration**.

## Key Behavior Change

### Before (Commercial CCTV Mode)
- ❌ One continuous file per motion event
- ❌ File duration = motion duration
- ❌ `chunk_duration` setting was ignored

### After (Fixed-Duration Chunks)
- ✅ Fixed-duration chunks based on `chunk_duration` setting
- ✅ Multiple chunks per recording session
- ✅ Predictable file sizes
- ✅ `chunk_duration` actually controls chunk length

## How It Works Now

### Example 1: Short Motion (5s) with 8s chunks
```
Motion Duration: 5 seconds
chunk_duration: 8 seconds

Result: 1 chunk of 8 seconds
File: Camera_1234567890_00000.mp4 (8s)
```

### Example 2: Long Motion (20s) with 8s chunks
```
Motion Duration: 20 seconds
chunk_duration: 8 seconds

Result: 3 chunks
Files:
  - Camera_1234567890_00000.mp4 (8s)
  - Camera_1234567890_00001.mp4 (8s)
  - Camera_1234567890_00002.mp4 (4s)
```

### Example 3: With Retrigger
```
Motion 1: 5 seconds
Gap: 3 seconds (within 5s retrigger)
Motion 2: 4 seconds
chunk_duration: 8 seconds

Result: 2 chunks (same session)
Files:
  - Camera_1234567890_00000.mp4 (8s)
  - Camera_1234567890_00001.mp4 (4s)
```

## Technical Implementation

### 1. hardware_pipeline.py Changes

**Switched from `qtmux + filesink` to `splitmuxsink`:**

```python
# OLD (ignored chunk_duration)
'!', 'qtmux',
'!', 'filesink',
f'location={output_file}',

# NEW (respects chunk_duration)
'!', 'splitmuxsink',
f'location={output_pattern}',
f'max-size-time={chunk_duration_ns}',
'muxer-factory=qtmux',
```

**Benefits of splitmuxsink:**
- Automatically splits at specified time intervals
- Creates sequential numbered files (00000, 00001, etc.)
- Handles file finalization properly
- No manual chunk management needed

### 2. streamer.py Changes

**Added session-based chunk uploading:**

```python
def _upload_session_chunks(self, session_start_time):
    """Upload all chunks created during a recording session"""
    # Find all chunks: stream_id_timestamp_*.mp4
    # Upload each chunk individually
```

**Pipeline manager now:**
- Tracks recording session start time
- Creates filename pattern instead of single filename
- Uploads all chunks from session after retrigger timeout

### 3. File Naming Convention

**Pattern:** `{stream_id}_{session_timestamp}_{chunk_number}.mp4`

**Examples:**
```
Pantry_1735712345_00000.mp4   (First chunk of session)
Pantry_1735712345_00001.mp4   (Second chunk)
Pantry_1735712345_00002.mp4   (Third chunk)
Office_1735712890_00000.mp4   (Different camera/session)
```

## Configuration

### Per-Camera Settings (config.yaml)
```yaml
streams:
- id: Pantry
  chunk_duration: 8           # Fixed chunk size (5-15s)
  retrigger_time: 5          # Wait time before ending session
  max_clip_length: 300       # Max session duration
  chunking_enabled: true
```

### Chunk Duration Options

| Setting | Behavior | Use Case |
|---------|----------|----------|
| 5s | Very frequent splits | Real-time monitoring, quick access |
| 8s | Balanced | Most scenarios |
| 10s | Moderate splits | Reduce file count |
| 15s | Fewer files | Longer reviews, storage optimization |

## Interaction with Other Settings

### With Retrigger Time
- **Purpose**: Prevent multiple recording sessions for brief gaps
- **Behavior**: Continues same session if motion resumes within retrigger window
- **Result**: All chunks from retriggered motion use same timestamp

```
Motion → Chunks with timestamp_1
Gap (within retrigger) → Keep session alive
Motion → More chunks with same timestamp_1
Gap (exceeds retrigger) → End session
Motion → New chunks with timestamp_2
```

### With Max Clip Length
- **Purpose**: Prevent extremely long recording sessions
- **Behavior**: Stops session and starts new one after max duration
- **Result**: New timestamp for continued recording

```
Session 1 (0-300s): camera_1000_*.mp4
  ├─ camera_1000_00000.mp4 (8s)
  ├─ camera_1000_00001.mp4 (8s)
  └─ ... (many chunks)

Session 2 (300s+): camera_1300_*.mp4
  ├─ camera_1300_00000.mp4 (8s)
  └─ ...
```

## Storage Impact

### File Count Comparison (1 minute of continuous motion)

| chunk_duration | Number of Files |
|----------------|-----------------|
| 5s | 12 files |
| 8s | 8 files |
| 10s | 6 files |
| 15s | 4 files |

### File Size (approximate, 2Mbps bitrate)

| Duration | File Size |
|----------|-----------|
| 5s | ~1.2 MB |
| 8s | ~2.0 MB |
| 10s | ~2.5 MB |
| 15s | ~3.7 MB |

## Upload Behavior

### Session Upload Process
1. Motion ends
2. Wait for retrigger_time
3. No motion detected → Stop recording
4. Find all chunks from session (matching timestamp pattern)
5. Upload each chunk individually
6. Chunks uploaded in sequential order

### Cloud Upload Queue
```
[Upload Queue]
├─ Pantry_1735712345_00000.mp4 → Uploading...
├─ Pantry_1735712345_00001.mp4 → Queued
├─ Pantry_1735712345_00002.mp4 → Queued
└─ Office_1735712890_00000.mp4 → Queued
```

## Benefits

### 1. Predictable File Sizes
- Easy to calculate storage needs
- Consistent network usage per chunk
- Better for bandwidth planning

### 2. Easier Browsing
- Shorter files easier to scrub through
- Find specific moments faster
- Better thumbnail generation

### 3. Better for Streaming
- Smaller chunks load faster
- Can start playback immediately
- Progressive download friendly

### 4. Storage Optimization
- Can adjust chunk_duration to balance file count vs. size
- Easier to implement retention policies
- Better for cloud storage costs

### 5. Reliability
- Smaller files less likely to corrupt
- Failed upload affects fewer seconds
- Easier to retry individual chunks

## Backward Compatibility

### Config Migration
✅ **Fully backward compatible**
- Existing configs work without changes
- `chunk_duration` defaults to 5 seconds if not specified
- Old single-file uploads still supported (if chunks not found)

### Testing Checklist

After updating, verify:
- [ ] Motion detection triggers recording
- [ ] Chunks created with correct duration
- [ ] Multiple chunks for long motion
- [ ] Single chunk for short motion
- [ ] Retrigger continues same session
- [ ] Max clip length starts new session
- [ ] All chunks uploaded after session
- [ ] File naming follows pattern
- [ ] Cloud upload succeeds

## Common Scenarios

### Scenario 1: Quick Motion (Person Walking By)
```yaml
Motion: 3 seconds
chunk_duration: 8s
retrigger_time: 5s

Result:
├─ Recording starts at motion
├─ Creates 8-second chunk (includes 3s motion + 5s retrigger wait)
└─ Uploads 1 chunk (8s)
```

### Scenario 2: Continuous Activity (Busy Office)
```yaml
Motion: 45 seconds continuous
chunk_duration: 10s
retrigger_time: 5s

Result:
├─ Creates 5 chunks: 10s, 10s, 10s, 10s, 5s
├─ All chunks same session (same timestamp)
└─ Uploads 5 chunks
```

### Scenario 3: Intermittent Motion (with Retrigger)
```yaml
Motion 1: 5s → Gap: 3s → Motion 2: 4s → Gap: 3s → Motion 3: 2s
chunk_duration: 8s
retrigger_time: 5s (gaps are within retrigger)

Result:
├─ One continuous session (14 seconds total)
├─ Creates 2 chunks: 8s, 6s
└─ Uploads 2 chunks
```

### Scenario 4: Very Long Recording (Hit Max Length)
```yaml
Motion: 400 seconds continuous
chunk_duration: 8s
max_clip_length: 300s

Result:
Session 1 (0-300s):
├─ 38 chunks of 8s each (304s total)
└─ Uploads all 38 chunks

Session 2 (300-400s):
├─ 13 chunks of 8s each (104s total)
└─ Uploads all 13 chunks

Total: 51 chunks, 2 sessions
```

## Troubleshooting

### Problem: Chunks not created
**Check:**
- GStreamer installed with splitmuxsink support
- `chunking_enabled: true` in config
- Check logs for pipeline errors

### Problem: Wrong chunk duration
**Check:**
- `chunk_duration` value in config (5-15 range)
- UI shows correct value
- Restart streams after config change

### Problem: Too many small files
**Solution:**
- Increase `chunk_duration` (e.g., 8s → 15s)
- Increase `retrigger_time` to combine events
- Adjust `motion_sensitivity` to reduce false positives

### Problem: Chunks not uploading
**Check:**
- Cloud upload enabled in config
- Network connectivity
- Check upload queue in dashboard
- Verify filename pattern matches expected format

## Performance Notes

### CPU/GPU Usage
- No change in encoding performance
- Same NVENC/NVDEC acceleration
- Minimal overhead from splitmuxsink

### Disk I/O
- Multiple file writes instead of single file
- GStreamer handles buffering efficiently
- `async-finalize=true` prevents blocking

### Network Impact
- Chunks uploaded sequentially
- Can implement parallel upload in future
- Smaller chunks = more consistent bandwidth usage

## Future Enhancements

Potential improvements:
- [ ] Parallel chunk upload for faster processing
- [ ] Adaptive chunk duration based on motion frequency
- [ ] Chunk preview thumbnails in UI
- [ ] Smart chunking at scene changes
- [ ] Chunk merging for very short sessions
- [ ] Configurable chunk overlap for continuity

## Summary

✅ **Fixed-duration chunking implemented**
✅ **chunk_duration setting now actually controls chunk length**
✅ **Works with motion detection, retrigger, and max clip length**
✅ **Predictable file sizes and storage usage**
✅ **All chunks from session uploaded automatically**
✅ **Fully backward compatible**

The system now provides true fixed-duration video chunks, making it easier to manage storage, predict bandwidth usage, and browse recordings!
