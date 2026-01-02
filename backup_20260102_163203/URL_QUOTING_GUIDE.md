# How to Test RTSP Decoder with URLs Containing & and ?

## ⚠️ IMPORTANT: URL Quoting

When your RTSP URL contains special characters like `&` or `?`, you **MUST** quote it in the shell:

### ❌ WRONG (shell interprets & as background process):
```bash
python troubleshoot_rtsp_decoder.py rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0
```
**Result**: URL becomes `rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1` (missing `&subtype=0`)

### ✅ CORRECT (properly quoted):
```bash
python troubleshoot_rtsp_decoder.py 'rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0'
```
**Result**: Full URL is passed correctly

## Quick Test Commands

### Option 1: Use the test script (easiest)
```bash
./test_decoders.sh
```
This handles URL quoting automatically and lets you test all cameras interactively.

### Option 2: Manual testing (remember to quote!)

#### Test with troubleshoot script:
```bash
# Camera 1 (Pantry)
python troubleshoot_rtsp_decoder.py 'rtsp://admin:tapway123@192.168.0.14:554/cam/realmonitor?channel=1&subtype=0'

# Camera 2 (Office Window)
python troubleshoot_rtsp_decoder.py 'rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0'

# Camera 3 (Office Entrance)
python troubleshoot_rtsp_decoder.py 'rtsp://admin:tapway123@192.168.0.198:554/cam/realmonitor?channel=1&subtype=0'
```

#### Test with diagnose script:
```bash
python diagnose_decoder.py 'rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0'
```

## Why This Matters

In bash/zsh, the `&` character means "run in background". So:
```bash
command arg1 & arg2
```
Becomes: "Run `command arg1` in background, then run `arg2` as a separate command"

By quoting the URL with single quotes `'...'`, the shell treats it as a single argument.

## Alternative: Escape Characters

You can also escape special characters:
```bash
python troubleshoot_rtsp_decoder.py rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1\&subtype=0
```

But **quoting is simpler and safer**.

## Verification

Both scripts now show URL validation:
```
RTSP URL: rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0
✓ URL parameters: channel=1&subtype=0
```

If you see this, the URL was passed correctly! ✅

If the parameters are missing, you forgot to quote the URL. ❌
