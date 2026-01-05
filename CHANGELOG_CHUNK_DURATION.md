# Changelog: Chunk Duration Range Update

## Date: January 5, 2026

## Change Summary
Updated video chunk duration configuration range from **5-10 seconds** to **5-15 seconds**.

## Motivation
- Provide more flexibility for users who want longer chunk durations
- Reduce file count for scenarios with continuous motion
- Better align with different use cases (real-time vs. review-focused)

## What Changed

### Configuration Range
- **Before**: 5-10 seconds
- **After**: 5-15 seconds

### Files Modified

1. **templates/index.html**
   - Updated chunk duration input `min="5" max="15"`
   - Updated label text from "Chunk Duration (5-10s)" to "Chunk Duration (5-15s)"

2. **TAPWAY_FEATURES.md**
   - Updated documentation to show chunk_duration range
   - Added example configuration

3. **TAPWAY_QUICKSTART.md**
   - Added Chunk Duration to settings list
   - Added Chunk Duration Guide table with use cases

4. **IMPLEMENTATION_SUMMARY.md**
   - Updated dashboard UI example to show chunk duration

5. **VISUAL_GUIDE.md**
   - Updated visual examples to include chunk duration display

## Use Cases by Duration

### 5 seconds (Default)
- **Best for**: Real-time monitoring
- **Pros**: Quick access to recent events, minimal delay
- **Cons**: More files to manage
- **File size**: ~8-15 MB per chunk

### 8-10 seconds
- **Best for**: Balanced approach
- **Pros**: Good balance between file count and accessibility
- **Cons**: None significant
- **File size**: ~15-25 MB per chunk

### 12-15 seconds
- **Best for**: Reducing file count, easier review
- **Pros**: Fewer files, easier to browse timeline
- **Cons**: Slightly longer delay to find specific moment
- **File size**: ~25-35 MB per chunk

## Configuration Example

```yaml
streams:
- id: Pantry
  name: Camera 192.168.0.14
  chunk_duration: 15          # Now supports up to 15 seconds
  chunking_enabled: true
```

## User Interface

Dashboard now shows:
```
Chunk Duration (5-15s): [input field]
```

Users can now set any value between 5-15 seconds for each camera.

## Backward Compatibility

✅ **Fully backward compatible**
- Existing configurations with 5-10 second values continue to work
- No migration needed
- Default remains 5 seconds

## Testing Recommendations

After updating, test with different chunk durations:

1. **Test 5s chunks**: Verify default behavior unchanged
2. **Test 10s chunks**: Verify middle range works
3. **Test 15s chunks**: Verify new maximum works
4. **Test invalid values**: UI should prevent values outside 5-15 range

## Related Settings

Remember: Chunk duration is different from:
- **Max Clip Length** (30-600s): Maximum continuous recording duration
- **Retrigger Time** (1-30s): Wait time after motion ends

### Recommended Combinations

**High Activity Area (Office, Store)**
```yaml
chunk_duration: 5        # Quick access
retrigger_time: 3        # Quick retrigger
max_clip_length: 120     # 2-minute max clips
```

**Low Activity Area (Parking Lot, Warehouse)**
```yaml
chunk_duration: 15       # Fewer files
retrigger_time: 10       # Longer retrigger
max_clip_length: 300     # 5-minute max clips
```

**Balanced Setup (Home, Small Office)**
```yaml
chunk_duration: 8        # Balanced
retrigger_time: 5        # Standard
max_clip_length: 300     # Standard
```

## Performance Impact

No performance impact expected:
- Same encoding pipeline used
- Same hardware acceleration
- Only affects file splitting logic

## Storage Considerations

Longer chunks = fewer files but larger individual files:

**5s chunks**: 720 files/hour (if continuous recording)
**10s chunks**: 360 files/hour
**15s chunks**: 240 files/hour (67% reduction vs. 5s)

## Future Enhancements

Potential future improvements:
- [ ] Dynamic chunk duration based on motion frequency
- [ ] Adaptive chunking (longer during low activity)
- [ ] Chunk duration templates for common scenarios
- [ ] Warning if chunk duration > max_clip_length

## Summary

✅ Chunk duration now configurable from 5-15 seconds
✅ More flexibility for different monitoring scenarios
✅ Fully backward compatible
✅ Documentation updated across all files
✅ UI updated with new range

Users can now choose the optimal chunk size for their specific use case!
