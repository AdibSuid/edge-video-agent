# Fix GStreamer Detection Issue - Quick Guide

## Your Current Problem

The `rebuild_opencv_tx2.sh` script failed with:
```
ERROR: GStreamer was not enabled!
Please check the errors above and fix dependencies.
```

This happens because **pkg-config can't find GStreamer**, even though it may be installed.

## Why This Happens

Common causes:
1. **pkg-config not installed** before GStreamer (can't find anything)
2. **Wrong installation order** - GStreamer installed before pkg-config
3. **Missing development packages** - only runtime installed, not -dev packages
4. **Corrupted package database** - apt cache issues

## Quick Fix (2 minutes)

### Step 1: Pull Latest Changes

```bash
cd /path/to/edge-video-agent
git pull origin jetson
```

This gets the updated scripts with fixes.

### Step 2: Run Diagnostic

```bash
chmod +x diagnose_gstreamer.sh
./diagnose_gstreamer.sh
```

This will show you **exactly** what's missing.

### Step 3: Auto-Fix Dependencies

```bash
chmod +x fix_gstreamer_deps.sh
./fix_gstreamer_deps.sh
```

This installs everything in the **correct order**.

### Step 4: Clean Previous Build

```bash
# Remove the failed build directory
rm -rf ~/opencv_build/opencv-*/build/*
```

This removes CMake cache that may have stored the "not found" result.

### Step 5: Retry OpenCV Build

```bash
./rebuild_opencv_tx2.sh
```

Should now show:
```
✓ GStreamer support: ENABLED
```

---

## Manual Fix (if auto-fix doesn't work)

### Check pkg-config First

```bash
# Is pkg-config installed?
command -v pkg-config
# Should show: /usr/bin/pkg-config

# If not found:
sudo apt-get install pkg-config
```

### Install GStreamer in Correct Order

```bash
# Update package list
sudo apt-get update

# Install pkg-config FIRST
sudo apt-get install -y pkg-config

# Install GStreamer base
sudo apt-get install -y \
    libgstreamer1.0-0 \
    libgstreamer1.0-dev

# Install GStreamer plugins base
sudo apt-get install -y \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-base

# Install additional plugins
sudo apt-get install -y \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools
```

### Verify Installation

```bash
# Test pkg-config can find GStreamer
pkg-config --exists gstreamer-1.0 && echo "✓ OK" || echo "✗ NOT FOUND"

# Check version
pkg-config --modversion gstreamer-1.0

# Should show something like: 1.14.5
```

### Clean and Retry

```bash
# Remove old build
rm -rf ~/opencv_build/opencv-*/build/*

# Retry
./rebuild_opencv_tx2.sh
```

---

## What the Updated Script Does Differently

The new `rebuild_opencv_tx2.sh`:

1. ✅ **Installs pkg-config FIRST** (critical!)
2. ✅ **Verifies GStreamer before CMake**
3. ✅ **Shows detailed errors** if something fails
4. ✅ **Checks CMake logs** for GStreamer errors
5. ✅ **Better error messages** with fixes

---

## Troubleshooting

### Issue: "pkg-config: command not found"

```bash
sudo apt-get install pkg-config
```

### Issue: "gstreamer-1.0 not found" even after install

```bash
# Check where .pc files are
find /usr -name "gstreamer-1.0.pc" 2>/dev/null

# If found in unusual location, set PKG_CONFIG_PATH
export PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH

# Add to .bashrc to make permanent
echo 'export PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH' >> ~/.bashrc
```

### Issue: "Cannot compile test GStreamer program"

```bash
# Missing development tools
sudo apt-get install build-essential gcc

# Missing GStreamer headers
sudo apt-get install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
```

### Issue: Still fails after everything

```bash
# Nuclear option - completely reinstall GStreamer
sudo apt-get remove --purge 'gstreamer*'
sudo apt-get autoremove
sudo apt-get update

# Reinstall in correct order
./fix_gstreamer_deps.sh
```

---

## Quick Diagnostic Commands

Run these to check status:

```bash
# Check pkg-config
which pkg-config

# Check GStreamer via pkg-config
pkg-config --modversion gstreamer-1.0

# Check header files exist
ls -l /usr/include/gstreamer-1.0/gst/gst.h

# Check installed packages
dpkg -l | grep gstreamer | grep "^ii"

# Try compiling test program
cat > /tmp/test.c << 'EOF'
#include <gst/gst.h>
int main() { gst_init(NULL, NULL); return 0; }
EOF

gcc /tmp/test.c $(pkg-config --cflags --libs gstreamer-1.0) -o /tmp/test && echo "✓ Compile OK"
```

---

## Summary

**Problem**: CMake can't find GStreamer
**Root Cause**: pkg-config not installed or wrong order
**Solution**:
1. Pull latest code: `git pull origin jetson`
2. Run fix script: `./fix_gstreamer_deps.sh`
3. Clean build: `rm -rf ~/opencv_build/opencv-*/build/*`
4. Retry: `./rebuild_opencv_tx2.sh`

**New Scripts Available**:
- `diagnose_gstreamer.sh` - Find what's wrong
- `fix_gstreamer_deps.sh` - Auto-fix dependencies
- Updated `rebuild_opencv_tx2.sh` - Better error detection

Should work now! 🚀
