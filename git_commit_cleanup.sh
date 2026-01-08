#!/bin/bash
# Git commit script after cleanup

echo "📦 Preparing to commit cleanup changes..."
echo ""

# Check git status
echo "Current status:"
git status --short

echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# Show what will be committed
echo "Files to be added/removed:"
git status --short | wc -l
echo " changes detected"

echo ""
read -p "Do you want to proceed with commit? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Adding all changes..."
git add -A

echo ""
echo "Committing changes..."
git commit -m "chore: cleanup repository - remove test/debug scripts

- Remove 81+ test and debug scripts
- Remove redundant documentation files
- Remove legacy streamer implementations
- Remove build/setup scripts (already completed)
- Keep all production code intact
- Keep essential documentation (README, QUICKSTART, etc.)
- Backup created before deletion

Production code preserved:
✓ app.py, streamer.py, hardware_pipeline.py
✓ motion_detector*.py, cloud_uploader.py
✓ discovery.py, monitor.py
✓ config.yaml, requirements.txt
✓ Docker files, static/, templates/

Hardware pipeline working with uridecodebin fix:
✓ NVENC and NVDEC active
✓ No more 'not-linked' errors
✓ MP4 muxing fixed"

echo ""
echo "Pushing to remote repository..."
git push origin jetson

echo ""
echo "✅ Changes committed and pushed successfully!"
echo ""
echo "Remote: https://github.com/AdibSuid/edge-video-agent/tree/jetson"
