# Quick Start: Using Tapo-Style Features

## Step-by-Step Guide

### 1. Access the Dashboard
```bash
# Start the application
python app.py

# Open browser to:
http://localhost:5000
```

### 2. Configure Motion Sensitivity (Easy Method)

**On the main dashboard**, each camera card now has sliders:

1. **Sensitivity Slider** (0-255)
   - Move left = More sensitive (detects smaller movements)
   - Move right = Less sensitive (only major motion)
   - Default: 100
   - Changes apply immediately!

2. **Retrigger Slider** (1-30 seconds)
   - How long to wait after motion ends before creating new clip
   - Lower = More separate clips
   - Higher = Longer continuous clips
   - Default: 5 seconds

3. **Max Clip Length** (30-600 seconds)
   - Maximum duration of a single video file
   - Prevents extremely long files
   - Default: 300 seconds (5 minutes)

### 3. Set Up Detection Zones (Advanced)

Click the **"Zone Editor (Tapo-style)"** button on the dashboard.

#### Zone Editor Steps:

1. **Select Camera**
   - Choose which camera to configure from dropdown

2. **Choose Zone Mode**
   - **"Apply to All Cameras"**: Same zones for all cameras
   - **"Individual per Camera"**: Different zones per camera

3. **Capture Frame**
   - Click "Capture Frame" button
   - Waits a moment, then shows camera snapshot

4. **Draw Zones**
   - Click and drag on the image to draw rectangles
   - Each rectangle = one detection zone
   - Can draw multiple zones
   - Only motion inside these zones will trigger recording

5. **Adjust Settings**
   - Use sliders to fine-tune sensitivity and timing
   - See real-time preview of values

6. **Save**
   - Click "Save Zones" button
   - Settings apply immediately to active streams

### 4. Testing Your Configuration

#### Test Motion Detection:
```bash
# Watch the logs
tail -f logs/<camera_id>.log

# Look for:
"MOTION ACTIVE"     # Motion detected
"MOTION INACTIVE"   # Motion ended
"Retrigger time elapsed"  # Recording stopped
```

#### Check Generated Clips:
```bash
# View recorded clips
ls -lh tmp/chunks/

# Example output:
Pantry_1735712345.mp4       # 5 minutes of motion
OfficeWindow_1735712890.mp4 # 2 minutes of motion
```

## Usage Scenarios

### Scenario 1: Reduce False Alarms (Windy Trees)

**Problem**: Outdoor camera triggers on moving leaves/branches

**Solution**:
1. Increase sensitivity value to 150-200 (less sensitive)
2. Draw zones to exclude tree areas
3. Increase retrigger time to 10-15 seconds

**Settings**:
```
Sensitivity: 180
Retrigger: 15s
Max Clip: 300s
Zones: Draw zone only on driveway/walkway area
```

### Scenario 2: Capture All Motion (High Security)

**Problem**: Need to catch every movement, even small ones

**Solution**:
1. Decrease sensitivity to 20-50 (very sensitive)
2. No zones (detect entire frame)
3. Low retrigger time (3-5 seconds)

**Settings**:
```
Sensitivity: 30
Retrigger: 3s
Max Clip: 600s (longer clips allowed)
Zones: None (or entire frame)
```

### Scenario 3: Office Door Monitoring

**Problem**: Only want to record when someone enters/exits door

**Solution**:
1. Moderate sensitivity (80-120)
2. Draw zone only around doorway
3. Medium retrigger (5-10 seconds)

**Settings**:
```
Sensitivity: 100
Retrigger: 8s
Max Clip: 120s (2 min clips)
Zones: Draw rectangle around door only
```

### Scenario 4: Busy Parking Lot

**Problem**: Constant activity, don't want 10-minute files

**Solution**:
1. Higher sensitivity (120-160) to ignore small cars passing
2. Lower max clip length (60-120s)
3. Short retrigger (3-5s)

**Settings**:
```
Sensitivity: 140
Retrigger: 5s
Max Clip: 90s (splits long recordings)
Zones: Focus on parking spots, not street
```

## Common Settings Explained

### Sensitivity Values Guide

| Value | Description | Use Case |
|-------|-------------|----------|
| 0-50 | **Very High** | Indoor, controlled lighting, need to catch everything |
| 50-100 | **High** | General indoor monitoring |
| 100-150 | **Medium** (Default) | Balanced for most scenarios |
| 150-200 | **Low** | Outdoor with some movement (trees, flags) |
| 200-255 | **Very Low** | Very windy areas, only detect people/vehicles |

### Retrigger Time Guide

| Value | Behavior | Use Case |
|-------|----------|----------|
| 1-3s | Quick separate clips | High traffic areas, need individual events |
| 5-10s | Balanced | Most scenarios (default: 5s) |
| 15-30s | Long continuous clips | Areas with intermittent motion |

### Max Clip Length Guide

| Value | File Size | Use Case |
|-------|-----------|----------|
| 30-60s | ~10-20 MB | Short events, save storage |
| 120-180s | ~40-60 MB | Medium events |
| 300s (5min) | ~100 MB | Default, good balance |
| 600s (10min) | ~200 MB | Long events, parking lots |

## Verification Checklist

After configuring, verify:

- [ ] Motion detection still working (check logs)
- [ ] Clips being created in `tmp/chunks/`
- [ ] Clip durations match expectations
- [ ] No excessive false alarms
- [ ] Zones showing correct areas
- [ ] Settings saved in `config.yaml`

## Troubleshooting Quick Fixes

### "Zone Editor shows black screen"
```bash
# Check camera is accessible
curl -I rtsp://admin:pass@<camera_ip>:554/...

# Try capturing frame manually
# In Zone Editor, click "Capture Frame" again
```

### "Settings not saving"
```bash
# Check config file permissions
ls -l config.yaml

# Should see: -rw-r--r--
# If not, fix with:
chmod 644 config.yaml
```

### "Motion not triggering"
1. Check sensitivity is not too high (lower the value)
2. Verify zones are not excluding the motion area
3. Check `motion_min_area` in config.yaml (try 1000 instead of 5000)

### "Too many clips created"
1. Increase retrigger time (5s → 15s)
2. Increase sensitivity value (less sensitive)
3. Add zones to exclude problem areas

## Advanced Tips

### Copy Settings Across Cameras

If zone_mode is "all", settings apply to all cameras automatically!

To copy individual camera settings:
1. Note down settings from Camera 1
2. Select Camera 2 in Zone Editor
3. Apply same values
4. Click Save

### Backup Your Configuration

```bash
# Backup config with zones
cp config.yaml config.yaml.backup

# Restore if needed
cp config.yaml.backup config.yaml
```

### Monitor in Real-Time

```bash
# Watch all camera logs at once
tail -f logs/*.log | grep -E "MOTION|Retrigger|Max clip"
```

### View Zone Coordinates

```bash
# See zone coordinates in config
grep -A5 "motion_zones" config.yaml
```

## Next Steps

1. ✅ Configure basic sensitivity on dashboard
2. ✅ Test with real motion
3. ✅ Fine-tune using Zone Editor
4. ✅ Adjust retrigger time based on your needs
5. ✅ Set appropriate max clip lengths
6. ✅ Monitor for a day, adjust as needed

## Support

If you need help:
1. Check `TAPO_FEATURES.md` for detailed documentation
2. Review logs: `logs/<camera_id>.log`
3. Test with different sensitivity values
4. Verify zones are correctly drawn

Enjoy your Tapo-style motion detection! 🎥
