# Visual Guide: Tapway-Style Motion Detection

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

## Recording Behavior with Fixed Chunk Duration

### Example: 8-Second Chunks with Retrigger

```
Timeline (seconds):
0    8    16   24   32   40   48   56   64
│────│────│────│────│────│────│────│────│
│                                        
│ Motion Detected (5s duration)
├─► Start Recording Session
│   └─► Create chunk1.mp4 (8s)
│
│        Motion Ends at 5s
│        Wait retrigger (5s)
│
│                No more motion
│                (Retrigger elapsed at 10s)
│                ↓
│────────────────│───────────────────────
                 Stop & Upload chunk1.mp4
                 (8 seconds total)


Example 2: Long Motion (20s)
├─► Motion Start
│   └─► chunk1.mp4 (0-8s)
│       └─► chunk2.mp4 (8-16s)
│           └─► chunk3.mp4 (16-20s = 4s chunk)
│
│                    Motion Ends
│                    Wait retrigger (5s)
│                    ↓
│────────────────────│──────────────────
                     Stop & Upload all 3 chunks
```

### Without Fixed Chunks (Old Behavior - Not Used)

```
Timeline:
0    5    10   15   20   25   30   35   40
│────│────│────│────│────│────│────│────│

Motion (5s) → One 5-second file
Motion Ends → Stop recording immediately

Result: File duration = Motion duration ❌
```

### With Fixed Chunks (Current Behavior)

```
Timeline:
0    5    10   15   20   25   30   35   40
│────│────│────│────│────│────│────│────│

Motion (5s) → One 8-second file (chunk_duration=8s)
Motion Ends → Continue to complete chunk
            → Stop at 8s mark

Result: File duration = chunk_duration setting ✅
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
│  │ Duration: 5s     │  │ Duration: 10s    │          │
│  │                  │  │                  │          │
│  │ Tapway Recording   │  │ Tapway Recording   │          │
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

### Scenario: Person walks through office (5 seconds of motion)

**With chunk_duration = 8 seconds:**
```
tmp/chunks/
└── Office_1735712345_00000.mp4  (8 seconds)
```

**With chunk_duration = 5 seconds:**
```
tmp/chunks/
└── Office_1735712345_00000.mp4  (5 seconds)
```

### Scenario: Continuous activity for 25 seconds

**With chunk_duration = 8 seconds:**
```
tmp/chunks/
├── Pantry_1735712000_00000.mp4  (8 seconds)
├── Pantry_1735712000_00001.mp4  (8 seconds)
├── Pantry_1735712000_00002.mp4  (8 seconds)
└── Pantry_1735712000_00003.mp4  (1 second)
```

**With chunk_duration = 15 seconds:**
```
tmp/chunks/
├── Pantry_1735712000_00000.mp4  (15 seconds)
└── Pantry_1735712000_00001.mp4  (10 seconds)
```

### Scenario: Multiple motion events with 10s retrigger

**Timeline:**
- Motion 1: 0-5 seconds (5s motion)
- Gap: 5-12 seconds (7s no motion, within retrigger)
- Motion 2: 12-15 seconds (3s motion)

**With chunk_duration = 8 seconds:**
```
tmp/chunks/
├── Office_1735712000_00000.mp4  (8 seconds, covers 0-8s)
└── Office_1735712000_00001.mp4  (7 seconds, covers 8-15s)

Total: 2 chunks for one recording session
```

## Benefits Visualization

```
Traditional CCTV          │  Tapway-Style System
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
1. ✅ Visual zone configuration (Tapway-style)
2. ✅ Per-camera sensitivity control
3. ✅ Smart retrigger (no duplicate clips)
4. ✅ Max clip length enforcement
5. ✅ Real-time updates
6. ✅ Hardware acceleration maintained

All with an intuitive interface matching commercial Tapway cameras! 🎉
