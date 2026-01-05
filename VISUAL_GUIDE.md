# Visual Guide: Tapo-Style Motion Detection

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Browser (User)                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Dashboard   │  │ Zone Editor  │  │  Settings    │    │
│  │  - Sliders   │  │  - Draw      │  │  - Config    │    │
│  │  - Status    │  │  - Zones     │  │  - Upload    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │
          │ REST API         │ REST API         │ REST API
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      Flask App (app.py)                     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Routes     │  │   API        │  │   Config     │    │
│  │   /          │  │   /api/*     │  │   YAML       │    │
│  │   /zones     │  │   /snapshot  │  │   Manager    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                   Streamer Instances                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Camera 1 (Pantry)                                  │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │  │
│  │  │Motion Detect │→ │   Pipeline   │→ │ Video    │  │  │
│  │  │ - Zones      │  │   Manager    │  │ Files    │  │  │
│  │  │ - Sensitivity│  │   - Retrigger│  │          │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Camera 2 (Office)                                  │  │
│  │  [Similar structure...]                             │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│              Hardware Pipeline (GStreamer)                  │
│                                                             │
│   RTSP → NVDEC → NVVIDCONV → NVENC → MP4                  │
│  (Camera) (HW     (GPU       (HW     (File)               │
│           Decode)  Process)  Encode)                       │
└─────────────────────────────────────────────────────────────┘
```

## Zone Configuration Flow

```
User Action                    System Response
═══════════════════════════════════════════════════════════

1. Open Zone Editor           Load camera list
   Click "Zone Editor"   →    Display dropdown
                              Load current zones
                              
2. Select Camera              Fetch camera snapshot
   Choose "Pantry"       →    GET /api/snapshot/Pantry
                              Display image on canvas
                              
3. Draw Zone                  Track mouse coordinates
   Click & Drag          →    Draw green rectangle
                              Store normalized coords
                              
4. Add More Zones            Repeat drawing
   Draw again            →    Multiple zones supported
                              Each stored separately
                              
5. Adjust Settings           Update live values
   Move sliders          →    Display current values
                              No save yet
                              
6. Save Configuration        POST to API
   Click "Save Zones"    →    Update config.yaml
                              Restart streamers
                              Apply new settings
```

## Motion Detection with Zones

### Before (No Zones)
```
┌───────────────────────────────┐
│                               │
│    Entire Frame Monitored     │
│                               │
│  [Tree]    [Door]    [Car]    │
│    ↓         ↓         ↓      │
│  MOTION   MOTION   MOTION     │
│                               │
│  Result: Many false alarms    │
│  from trees and passing cars  │
└───────────────────────────────┘
```

### After (With Zones)
```
┌───────────────────────────────┐
│                               │
│  [Tree]  ┌─────────┐  [Car]  │
│          │  Door   │          │
│  (ignored)│       │(ignored)  │
│          │ ZONE 1  │          │
│          └────┬────┘          │
│               ↓               │
│            MOTION             │
│                               │
│  Result: Only door activity   │
│  triggers recording           │
└───────────────────────────────┘
```

## Retrigger Time Behavior

### Example: 5-Second Retrigger

```
Timeline (seconds):
0    5    10   15   20   25   30   35   40
│────│────│────│────│────│────│────│────│
│                                        
│ Motion Detected
├─► Start Recording "clip1.mp4"
│
│                Motion Continues
│                ↓
│────────────────│───────────────────────
│                Still recording clip1.mp4
│
│                          Motion Ends
│                          ↓
│──────────────────────────│─────────────
│                          Start 5s timer
│
│                             Motion Again!
│                             (Within 5s)
│                             ↓
│─────────────────────────────│──────────
│                             Continue clip1.mp4
│                             (Retriggered!)
│
│                                   Motion Ends
│                                   ↓
│───────────────────────────────────│────
│                                   Start 5s timer
│
│                                        No Motion
│                                        (5s elapsed)
│                                        ↓
│────────────────────────────────────────│
                                         Stop & Upload
                                         clip1.mp4
```

### Without Retrigger (Old Behavior)

```
Timeline:
0    5    10   15   20   25   30   35   40
│────│────│────│────│────│────│────│────│

Motion → Start clip1.mp4
Motion Ends → Stop clip1.mp4

     Motion → Start clip2.mp4
     Motion Ends → Stop clip2.mp4

                Motion → Start clip3.mp4
                Motion Ends → Stop clip3.mp4

Result: 3 separate clips for same event! ❌
```

### With 5s Retrigger (New Behavior)

```
Timeline:
0    5    10   15   20   25   30   35   40
│────│────│────│────│────│────│────│────│

Motion → Start clip1.mp4
   ├──── Continues recording ────┤
   Motion Ends... Motion Again!
                        │
                        └─► Same clip continues
                                  │
                                  Motion Ends
                                  Wait 5s...
                                          Stop & Upload

Result: 1 continuous clip for event! ✅
```

## Max Clip Length Example

### Scenario: 5-Minute Max, Continuous Motion

```
Time     Event                    File Status
═══════════════════════════════════════════════════════════
0:00     Motion Start             clip1.mp4 START
0:30     Still moving            clip1.mp4 recording
1:00     Still moving            clip1.mp4 recording
2:00     Still moving            clip1.mp4 recording
3:00     Still moving            clip1.mp4 recording
4:00     Still moving            clip1.mp4 recording
5:00     MAX LENGTH!             clip1.mp4 STOP & UPLOAD
         Motion continues        clip2.mp4 START
6:00     Still moving            clip2.mp4 recording
7:00     Still moving            clip2.mp4 recording
8:00     Still moving            clip2.mp4 recording
9:00     Still moving            clip2.mp4 recording
10:00    MAX LENGTH!             clip2.mp4 STOP & UPLOAD
         Motion continues        clip3.mp4 START
11:00    Still moving            clip3.mp4 recording
12:00    Motion ENDS             Wait retrigger (5s)
12:05    No more motion          clip3.mp4 STOP & UPLOAD

Result: 3 manageable files instead of 1 huge 12-minute file
```

## Sensitivity Comparison

### High Sensitivity (Value: 30)
```
Camera View:
┌───────────────────────────────┐
│  [Person] [Cat] [Leaf]        │
│     ↓       ↓      ↓          │
│   DETECT DETECT DETECT        │
│                               │
│  Result: Everything triggers! │
└───────────────────────────────┘
```

### Medium Sensitivity (Value: 100)
```
Camera View:
┌───────────────────────────────┐
│  [Person] [Cat] [Leaf]        │
│     ↓       ↓      ↓          │
│   DETECT DETECT  (ignore)     │
│                               │
│  Result: Balanced detection   │
└───────────────────────────────┘
```

### Low Sensitivity (Value: 200)
```
Camera View:
┌───────────────────────────────┐
│  [Person] [Cat] [Leaf]        │
│     ↓       ↓      ↓          │
│   DETECT (ignore) (ignore)    │
│                               │
│  Result: Only major motion    │
└───────────────────────────────┘
```

## Dashboard UI Layout

```
┌────────────────────────────────────────────────────────┐
│  Edge Agent Dashboard                                  │
│  [Discover] [Zone Editor] [Motion] [Event Log]        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Camera 1: Pantry │  │ Camera 2: Office │          │
│  ├──────────────────┤  ├──────────────────┤          │
│  │ Status: Active   │  │ Status: Idle     │          │
│  │ Motion: Yes 🟢   │  │ Motion: No  ⚫   │          │
│  │                  │  │                  │          │
│  │ ☑ Streaming      │  │ ☑ Streaming      │          │
│  │ ☑ Chunking       │  │ ☑ Chunking       │          │
│  │                  │  │                  │          │
│  │ Tapo Recording   │  │ Tapo Recording   │          │
│  │ ╶─╴╶─╴╶─╴╶─╴╶─╴ │  │ ╶─╴╶─╴╶─╴╶─╴╶─╴ │          │
│  │ Sens:  ─●────    │  │ Sens:  ───●──    │          │
│  │        100       │  │        150       │          │
│  │                  │  │                  │          │
│  │ Retrig: ──●───   │  │ Retrig: ─●────   │          │
│  │        5s        │  │        3s        │          │
│  │                  │  │                  │          │
│  │ MaxClip:──●───   │  │ MaxClip:───●──   │          │
│  │        300s      │  │        180s      │          │
│  └──────────────────┘  └──────────────────┘          │
└────────────────────────────────────────────────────────┘
```

## Zone Editor Interface

```
┌─────────────────────────────────────────────────────────────┐
│  Motion Detection Zone Editor                               │
│  [← Back to Dashboard]                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────┐  ┌──────────────────────┐│
│  │ Camera: [Pantry     ▼]      │  │ Settings             ││
│  │                             │  │                      ││
│  │ ┌───────────────────────┐   │  │ Zone Mode:           ││
│  │ │  [Camera Snapshot]    │   │  │ ◉ Apply to All      ││
│  │ │                       │   │  │ ○ Individual        ││
│  │ │  ┌──────┐            │   │  │                      ││
│  │ │  │Zone 1│            │   │  │ Motion Sensitivity   ││
│  │ │  └──────┘            │   │  │ ──○──────  100      ││
│  │ │            ┌──────┐  │   │  │                      ││
│  │ │            │Zone 2│  │   │  │ Retrigger Time       ││
│  │ │            └──────┘  │   │  │ ──○──────  5s       ││
│  │ └───────────────────────┘   │  │                      ││
│  │                             │  │ Max Clip Length      ││
│  │ [📷 Capture] [🗑 Clear]     │  │ ──○──────  300s     ││
│  │ [💾 Save Zones]             │  │                      ││
│  └─────────────────────────────┘  │ Active Zones (2)     ││
│                                   │ • Zone 1  [Delete]   ││
│                                   │ • Zone 2  [Delete]   ││
│                                   └──────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Configuration File Structure

```yaml
# Global defaults
motion_sensitivity: 100
motion_zones: []              # Used if zone_mode = "all"
retrigger_time: 5
max_clip_length: 300
zone_mode: "all"              # or "individual"

streams:
- id: Pantry
  name: Camera 192.168.0.14
  
  # Per-camera overrides (if zone_mode = "individual")
  motion_sensitivity: 100     # Override global
  motion_zones:               # Per-camera zones
    - [100, 50, 200, 150]    # [x, y, width, height]
    - [300, 200, 150, 100]   # Multiple zones
  retrigger_time: 5           # Per-camera retrigger
  max_clip_length: 300        # Per-camera max length
```

## File Output Examples

### Scenario: Person walks through office 3 times

**Without Retrigger:**
```
tmp/chunks/
├── Office_1735712345.mp4  (5 seconds)
├── Office_1735712358.mp4  (3 seconds)
└── Office_1735712372.mp4  (4 seconds)
```

**With 10s Retrigger:**
```
tmp/chunks/
└── Office_1735712345.mp4  (30 seconds, continuous)
```

### Scenario: 15-minute continuous motion with 5-minute max

**Result:**
```
tmp/chunks/
├── Pantry_1735712000.mp4  (300 seconds = 5 min)
├── Pantry_1735712300.mp4  (300 seconds = 5 min)
└── Pantry_1735712600.mp4  (300 seconds = 5 min)
```

## Benefits Visualization

```
Traditional CCTV          │  Tapo-Style System
──────────────────────────┼────────────────────────
24/7 Recording            │  Motion-only Recording
   ↓                      │     ↓
Huge Storage Needed       │  Minimal Storage
                          │
Fixed Sensitivity         │  Adjustable per Camera
   ↓                      │     ↓
Many False Alarms         │  Tuned Detection
                          │
No Zone Control           │  Visual Zone Editor
   ↓                      │     ↓
Detect Everything         │  Focus on Important Areas
                          │
CPU Encoding              │  Hardware Acceleration
   ↓                      │     ↓
High CPU Usage            │  Low CPU Usage
                          │
Multiple Short Clips      │  Smart Clip Management
   ↓                      │     ↓
Hard to Review            │  Easy to Review
```

## Summary

Your system now provides:
1. ✅ Visual zone configuration (Tapo-style)
2. ✅ Per-camera sensitivity control
3. ✅ Smart retrigger (no duplicate clips)
4. ✅ Max clip length enforcement
5. ✅ Real-time updates
6. ✅ Hardware acceleration maintained

All with an intuitive interface matching commercial Tapo cameras! 🎉
