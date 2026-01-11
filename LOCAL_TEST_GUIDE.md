# Local Testing Guide - RTMP Push to DeepStream

This guide helps you test the RTMP push implementation locally before deploying to cloud.

## Architecture - Local Test

```
Your Windows PC:
  ┌─────────────────────────────────────────────────┐
  │                                                 │
  │  Camera RTSP → Edge Agent (GStreamer)          │
  │                    ↓ RTMP Push                  │
  │              Local MediaMTX                     │
  │                    ↓ RTSP Output                │
  │         Mock DeepStream Server                  │
  │                                                 │
  └─────────────────────────────────────────────────┘
```

## Prerequisites

- MediaMTX binary (already have: mediamtx.exe)
- Python 3 (already have)
- Your 3 RTSP cameras accessible
- GStreamer installed (for RTMP push)

## Step-by-Step Testing

### Step 1: Start Local MediaMTX

**Terminal 1 (PowerShell):**
```powershell
cd C:\Users\adibc\Documents\edge-video-agent

# Start MediaMTX with local config
.\mediamtx.exe mediamtx-local.yml
```

**Expected output:**
```
INF MediaMTX v1.15.2
INF [RTMP] listener opened on :1935
INF [RTSP] listener opened on :8554
INF [HLS] listener opened on :8888
INF [API] listener opened on :9997
```

✅ **Verify MediaMTX is running:**
- RTMP port 1935 - ready to receive push
- RTSP port 8554 - ready to serve streams
- API port 9997 - monitoring

### Step 2: Start Mock DeepStream Server

**Terminal 2 (PowerShell in venv):**
```powershell
cd C:\Users\adibc\Documents\edge-video-agent
.\venv\Scripts\activate

# Start mock DeepStream REST API
python mock_deepstream_server.py
```

**Expected output:**
```
============================================================
🚀 MOCK DEEPSTREAM REST API SERVER
============================================================
Server running on: http://localhost:9002
Endpoints available:
  GET  /api/v1/health/get-dsready-state
  GET  /api/v1/stream/get-stream-info
  POST /api/v1/stream/add
  POST /api/v1/stream/remove

✅ Ready to receive streams from Edge Agent
```

### Step 3: Test Mock DeepStream

**Terminal 3 (test the API):**
```powershell
# Health check
curl http://localhost:9002/api/v1/health/get-dsready-state

# Should return: {"pipeline_ready":true,"status":"success",...}
```

### Step 4: Start Edge Agent (Local Test Mode)

**Terminal 4 (PowerShell in venv):**
```powershell
cd C:\Users\adibc\Documents\edge-video-agent
.\venv\Scripts\activate

# Use local test config
python app.py --config config-local-test.yaml
```

**OR modify app.py to accept config parameter, or just:**
```powershell
# Temporarily rename configs
move config.yaml config-cloud-backup.yaml
move config-local-test.yaml config.yaml

# Run normally
python app.py
```

### Step 5: Watch the Magic Happen! 🎉

**In Terminal 4 (Edge Agent), you should see:**
```
RTMP Push Manager initialized: rtmp://localhost:1935
✓ RTMP push started for Test2
  Source: rtsp://orinnano:orinnano@192.168.1.102:554/stream1
  Destination: rtmp://localhost:1935/live/Test2
✓ Added stream to DeepStream: Test2
  Cloud RTSP URL: rtsp://localhost:8554/live/Test2

✓ RTMP push started for Test3
  ...
✓ RTMP push started for test
  ...
```

**In Terminal 2 (Mock DeepStream), you should see:**
```
============================================================
📥 RECEIVED STREAM ADD REQUEST
============================================================
✓ Camera ID: Test2
✓ Camera Name: Camera 192.168.1.102
✓ Camera URL: rtsp://localhost:8554/live/Test2
✓ Change Type: camera_add

✅ Stream 'Test2' added successfully!
📊 Total streams: 1
============================================================
```

**In Terminal 1 (MediaMTX), you should see:**
```
INF [RTMP] [session] is publishing to path 'live/Test2', 2 tracks (H264, AAC)
INF [RTMP] [session] is publishing to path 'live/Test3', 2 tracks (H264, AAC)
INF [RTMP] [session] is publishing to path 'live/test', 2 tracks (H264, AAC)
```

## Verification Tests

### Test 1: Check Active Streams in Mock DeepStream
```powershell
curl http://localhost:9002/api/v1/stream/get-stream-info
```

**Expected response:**
```json
{
  "count": 3,
  "status": "success",
  "streams": [
    {
      "camera_id": "Test2",
      "camera_name": "Camera 192.168.1.102",
      "camera_url": "rtsp://localhost:8554/live/Test2",
      "status": "active"
    },
    {
      "camera_id": "Test3",
      ...
    },
    {
      "camera_id": "test",
      ...
    }
  ]
}
```

### Test 2: Verify RTSP Stream Output
```powershell
# Use ffplay or VLC to view the RTSP stream
ffplay rtsp://localhost:8554/live/Test2
# OR
vlc rtsp://localhost:8554/live/Test2
```

**You should see live video from Camera 192.168.1.102!**

### Test 3: Check MediaMTX API
```powershell
curl http://localhost:9997/v3/paths/list
```

**Should show all active paths:** `/live/Test2`, `/live/Test3`, `/live/test`

### Test 4: Test Auto-Restart

**Kill one GStreamer process and watch it auto-restart:**

1. Find the process:
```powershell
tasklist | findstr gst-launch
```

2. Kill one:
```powershell
taskkill /PID <pid> /F
```

3. Watch Edge Agent logs - should see:
```
RTMP push died for Test2 (exit code: 1)
Restarting RTMP push for Test2 in 2s (attempt 1)
✓ RTMP push restarted for Test2
```

## Test Results Summary

After successful local testing, you should confirm:

- ✅ **3 RTMP streams** pushed to local MediaMTX
- ✅ **3 RTSP streams** available from MediaMTX
- ✅ **3 streams added** to Mock DeepStream via REST API
- ✅ **JSON format** matches your cloud format exactly
- ✅ **Auto-restart** works when connection drops
- ✅ **Unique camera_id** for each stream

## When Cloud DeepStream is Ready

### Switch from Local to Cloud - Just 3 Changes!

**In config.yaml (or restore config-cloud-backup.yaml):**

```yaml
# Change 1: RTMP URL
cloud_rtmp_url: rtmp://47.250.210.53:1935  # was: rtmp://localhost:1935

# Change 2: DeepStream API URL
deepstream_api_url: http://47.250.210.53:9002  # was: http://localhost:9002

# Change 3: MediaMTX hostname
mediamtx_hostname: mediamtx  # was: localhost
```

**That's it! Everything else stays the same.**

## Troubleshooting

### "RTMP connection failed"
- Check MediaMTX is running on port 1935
- Check Windows Firewall allows port 1935

### "Stream not visible in RTSP"
- Wait 2-3 seconds after RTMP push starts
- Check MediaMTX logs for errors
- Verify camera RTSP URL is correct

### "Mock DeepStream not receiving"
- Check port 9002 is not in use: `netstat -ano | findstr 9002`
- Verify Edge Agent config points to localhost:9002

### "GStreamer not found"
- Install GStreamer: https://gstreamer.freedesktop.org/download/
- Add to PATH: `C:\gstreamer\1.0\x86_64\bin`

## Success Criteria

Your local test is successful when you can:

1. ✅ See all 3 cameras pushing RTMP
2. ✅ Play RTSP streams from MediaMTX
3. ✅ See streams registered in Mock DeepStream
4. ✅ Auto-restart works after killing a push

**When all green, you're ready for cloud deployment!** 🚀
