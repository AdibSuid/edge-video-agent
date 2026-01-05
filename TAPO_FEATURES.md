# Tapo-Style Motion Detection Features

## Overview
The system now includes **Tapo camera-inspired features** for motion detection and video recording. These features provide fine-grained control over motion sensitivity, detection zones, and recording behavior - just like commercial Tapo/TP-Link cameras.

## New Features Implemented

### 1. Motion Sensitivity Control
- **Per-camera sensitivity adjustment** (0-255 scale)
- **Global or individual settings**: Apply sensitivity to all cameras or customize per camera
- **Real-time adjustment**: Change sensitivity without restarting cameras
- Lower values = more sensitive to small movements
- Higher values = only detect major motion

### 2. Detection Zone Editor
- **Visual zone drawing interface** similar to Tapo mobile app
- **Multiple zones per camera**: Draw rectangular zones where motion should be detected
- **Zone modes**:
  - **All Cameras**: Apply the same zones to all cameras
  - **Individual**: Set different zones for each camera
- **Interactive canvas**: Click and drag to draw detection zones on live camera snapshot

### 3. Retrigger Time (Tapo's "Cool-down Period")
- **Configurable wait time** (1-30 seconds) after motion ends before starting a new clip
- Prevents creating multiple small clips for continuous activity
- Example: If someone walks through frame multiple times, system continues recording instead of creating many separate clips

### 4. Maximum Clip Length
- **Automatic clip splitting** when recording exceeds maximum duration (30s - 10 minutes)
- Prevents extremely long video files
- Automatically starts new clip when max length reached during continuous motion
- Default: 300 seconds (5 minutes)

### 5. Pre-record Buffer (Coming Soon)
- **Record before motion starts** (0-5 seconds)
- Captures what happened just before motion was detected
- Requires buffering implementation (currently set to 0)

## Configuration

### Global Settings (config.yaml)
```yaml
# Tapo-style Motion Detection Settings (Global defaults)
motion_sensitivity: 100        # 0-255, lower = more sensitive
motion_zones: []               # Global zones if zone_mode = "all"

# Tapo-style Recording Features
retrigger_time: 5             # Seconds to wait before starting new clip
pre_record_buffer: 0          # Seconds to record before motion (future feature)
max_clip_length: 300          # Maximum clip duration in seconds (5 min)
zone_mode: "all"              # "all" or "individual" zone application
```

### Per-Camera Settings (config.yaml)
```yaml
streams:
- id: Pantry
  name: Camera 192.168.0.14
  rtsp_url: rtsp://admin:pass@192.168.0.14:554/...
  
  # Per-camera motion settings (override global)
  motion_sensitivity: 100      # Per-camera sensitivity
  motion_zones: []             # Per-camera zones (if zone_mode = "individual")
  retrigger_time: 5           # Per-camera retrigger time
  max_clip_length: 300        # Per-camera max clip length
  pre_record_buffer: 0        # Per-camera pre-record buffer
```

## User Interface

### Dashboard Controls
Each camera card on the dashboard now includes:
- **Sensitivity slider** (0-255)
- **Retrigger time slider** (1-30s)
- **Max clip length slider** (30-600s)
- Real-time value display
- Instant apply on change

### Zone Editor Page
Access via: **Dashboard → Zone Editor (Tapo-style)** button

Features:
1. **Camera selection dropdown**
2. **Zone mode selector** (All cameras vs Individual)
3. **Live camera snapshot capture**
4. **Interactive canvas drawing**:
   - Click and drag to draw detection zones
   - Multiple zones supported
   - Visual overlay shows active zones
5. **Settings panel**:
   - Motion sensitivity slider
   - Retrigger time slider
   - Max clip length slider
   - Pre-record buffer slider
6. **Zone management**:
   - List of active zones
   - Delete individual zones
   - Clear all zones
   - Save configuration

## How It Works

### Recording Behavior with Retrigger Time

**Scenario 1: Motion with Retrigger**
```
Motion detected → Start recording (clip1.mp4)
Motion continues → Keep recording same clip
Motion ends → Wait retrigger_time (5s)
Motion detected again → Continue same clip (no new file!)
Motion ends → Wait retrigger_time (5s)
No motion for 5s → Stop recording, upload clip1.mp4
```

**Scenario 2: Max Clip Length Enforcement**
```
Motion detected → Start recording (clip1.mp4)
Recording for 300s → Max length reached
Motion still active → Stop clip1.mp4, start clip2.mp4
Continues recording → Another 300s → Stop clip2.mp4, start clip3.mp4
Motion ends → Wait retrigger_time → Upload final clip
```

### Detection Zones

**Zone Mode: "All"**
- Define zones once
- Applied to all cameras
- Good for: Outdoor cameras pointing at similar areas (e.g., all watching driveways)

**Zone Mode: "Individual"**
- Each camera has its own zones
- Good for: Different camera angles and purposes
  - Office camera: Detect only doorway
  - Pantry camera: Detect center area only
  - Entrance: Detect entire frame

### Sensitivity in Action

**High Sensitivity (Low Value: 0-50)**
- Detects small movements (cat walking, leaves moving)
- More false positives
- Good for: High security areas, detecting small objects

**Medium Sensitivity (Value: 50-150)**
- Balanced detection
- Default: 100
- Good for: General purpose monitoring

**Low Sensitivity (High Value: 150-255)**
- Only major motion (person walking)
- Fewer false positives
- Good for: Busy areas, windy locations with moving trees

## API Endpoints

### Get Camera Snapshot
```
GET /api/camera_snapshot/<stream_id>
```
Returns base64-encoded JPEG snapshot for zone drawing.

### Update Zone Settings
```
POST /api/zone_settings
Body: {
  "stream_id": "Pantry",
  "zone_mode": "individual",
  "zones": [
    {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6}
  ],
  "motion_sensitivity": 100,
  "retrigger_time": 5,
  "max_clip_length": 300,
  "pre_record_buffer": 0
}
```

## Comparison with Tapo Cameras

| Feature | Tapo App | This System |
|---------|----------|-------------|
| Motion Sensitivity | ✅ 10 levels | ✅ 256 levels (0-255) |
| Detection Zones | ✅ Visual drawing | ✅ Visual drawing |
| Zone per camera | ✅ Yes | ✅ Yes (individual mode) |
| Global zones | ❌ No | ✅ Yes (all mode) |
| Retrigger time | ✅ Yes | ✅ Yes (1-30s) |
| Max clip length | ✅ Yes | ✅ Yes (30-600s) |
| Pre-record buffer | ✅ Yes | 🚧 Coming soon |
| Hardware acceleration | ❌ No | ✅ NVENC/NVDEC |

## Advantages Over Tapo

1. **Hardware Acceleration**: Uses NVIDIA NVENC/NVDEC for better performance
2. **More sensitivity levels**: 256 levels vs Tapo's 10
3. **Global zones**: Apply same zones to multiple cameras at once
4. **Longer recordings**: Up to 10 minutes vs Tapo's typical 2-5 minutes
5. **Flexible retrigger**: 1-30 seconds vs Tapo's fixed intervals
6. **Open source**: Fully customizable
7. **Local processing**: No cloud dependency (optional cloud upload)

## Usage Examples

### Example 1: Office Monitoring
```yaml
# Office camera focused on doorway only
- id: Office
  motion_sensitivity: 80        # Moderate sensitivity
  motion_zones:                 # Only detect doorway area
    - [0.3, 0.2, 0.4, 0.6]     # x, y, width, height (normalized 0-1)
  retrigger_time: 10           # Wait 10s before new clip
  max_clip_length: 120         # 2-minute clips max
```

### Example 2: High-Security Entrance
```yaml
# Entrance camera - detect everything, very sensitive
- id: Entrance
  motion_sensitivity: 30        # High sensitivity
  motion_zones: []              # No zones = detect entire frame
  retrigger_time: 3            # Quick retrigger
  max_clip_length: 600         # 10-minute clips allowed
```

### Example 3: Outdoor with Trees
```yaml
# Outdoor camera with windy conditions
- id: Garden
  motion_sensitivity: 150       # Low sensitivity (ignore leaves)
  motion_zones:                 # Only detect pathway
    - [0.2, 0.5, 0.6, 0.4]     
  retrigger_time: 15           # Long retrigger (reduce false clips)
  max_clip_length: 300         # 5-minute clips
```

## Troubleshooting

### Too Many False Alarms
1. **Increase sensitivity value** (make it less sensitive)
2. **Add detection zones** to exclude problem areas
3. **Increase retrigger time** to combine short events

### Missing Motion Events
1. **Decrease sensitivity value** (make it more sensitive)
2. **Remove or expand zones**
3. **Check motion_min_area** setting (make it smaller)

### Clips Too Short
1. **Increase retrigger_time** (wait longer before ending)
2. **Decrease motion_cooldown** (faster motion detection)

### Clips Too Long
1. **Decrease max_clip_length**
2. **Check if continuous motion is real or false detection**

## Future Enhancements

- [ ] Pre-record buffer implementation (circular buffer)
- [ ] Smart detection (person vs vehicle vs animal)
- [ ] Heat map visualization showing motion hotspots
- [ ] Time-based zone schedules (different zones for day/night)
- [ ] Mobile app for zone drawing on phone/tablet
- [ ] Multi-zone detection with different sensitivities per zone

## Technical Notes

### Zone Storage Format
Zones are stored in normalized coordinates (0.0 to 1.0):
```python
{
  "x": 0.1,    # 10% from left
  "y": 0.2,    # 20% from top
  "w": 0.5,    # 50% of frame width
  "h": 0.6     # 60% of frame height
}
```

This ensures zones work across different resolutions.

### Retrigger Implementation
```python
# In streamer.py _pipeline_manager_loop
if not motion_active:
    if motion_end_time == 0:
        motion_end_time = time.time()
    
    elapsed = time.time() - motion_end_time
    if elapsed >= retrigger_time:
        # Stop recording
```

### Max Clip Length Implementation
```python
if recording_duration >= max_clip_length:
    # Stop current clip
    # Upload it
    # Start new clip if motion still active
```

## Summary

Your edge video agent now has **Tapo-style motion detection** with:
- ✅ Visual zone editor
- ✅ Per-camera sensitivity control
- ✅ Retrigger time (cool-down period)
- ✅ Maximum clip length enforcement
- ✅ Global or individual zone modes
- ✅ Real-time configuration updates
- ✅ Hardware-accelerated recording

All while maintaining the advantages of local processing, hardware acceleration, and open-source flexibility!
