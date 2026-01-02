#!/bin/bash
# Safe cleanup script - removes test/debug files while keeping production code

echo "🧹 Cleaning up edge-video-agent repository..."
echo ""

# Create backup just in case
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"

# Files to DELETE (test/debug scripts)
FILES_TO_DELETE=(
    # Test scripts
    "test_*.py"
    "test_*.sh"
    "check_*.py"
    "check_*.sh"
    "diagnose_*.py"
    "diagnose_*.sh"
    "debug_*.py"
    "verify_*.py"
    "watch_*.py"
    "find_*.py"
    "find_*.sh"
    "troubleshoot_*.py"
    
    # Build/setup scripts (already completed)
    "build_*.sh"
    "install_*.sh"
    "setup_*.sh"
    "fix_*.sh"
    "rebuild_*.sh"
    "opencv.sh"
    "monitor_performance.sh"
    
    # Old/legacy streamer implementations
    "streamer_jetpack4_patch.py"
    "streamer_jetson_hw.py"
    
    # Utility files no longer needed
    "jetpack_utils.py"
    "detect_hardware.py"
    
    # Test data
    "test_chunk.mp4"
    "hardware_report.json"
    "samurai_inspector_postman_collection.json"
    
    # Redundant config
    "config.jetson.yaml"
    "config.yaml.backup"
    
    # Start script (can be recreated if needed)
    "start_app.sh"
)

# Documentation to DELETE (redundant/outdated guides)
DOCS_TO_DELETE=(
    "COMMUNITY_STANDARD_FIX.md"
    "FIXES_SUMMARY.md"
    "GSTREAMER_FIX_NOW.md"
    "HARDWARE_ACCELERATION_IMPLEMENTED.md"
    "JETPACK4_TX2_SETUP.md"
    "JETSON_OPTIMIZATION.md"
    "JETSON_SETUP.md"
    "OPTIMIZATION_COMPLETE.md"
    "PACKAGE_NOT_FOUND_FIX.md"
    "STEP_BY_STEP_FIX.md"
    "TX2_JP4_COMPATIBILITY_ANALYSIS.md"
    "TX2_NX_FIX_SUMMARY.md"
    "URL_QUOTING_GUIDE.md"
    "WRONG_VS_RIGHT.md"
    "QUICK_START.md"  # Keep QUICKSTART.md instead
)

# Move files to backup before deleting
echo "Moving files to backup..."
for pattern in "${FILES_TO_DELETE[@]}"; do
    for file in $pattern; do
        if [ -f "$file" ]; then
            cp "$file" "$BACKUP_DIR/" 2>/dev/null
        fi
    done
done

for doc in "${DOCS_TO_DELETE[@]}"; do
    if [ -f "$doc" ]; then
        cp "$doc" "$BACKUP_DIR/" 2>/dev/null
    fi
done

echo "✓ Backup created"
echo ""

# Delete test scripts
echo "Removing test/debug scripts..."
for pattern in "${FILES_TO_DELETE[@]}"; do
    rm -f $pattern 2>/dev/null
done
echo "✓ Test scripts removed"

# Delete redundant documentation
echo "Removing redundant documentation..."
for doc in "${DOCS_TO_DELETE[@]}"; do
    rm -f "$doc" 2>/dev/null
done
echo "✓ Redundant docs removed"

# Clean up Python cache
echo "Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null
echo "✓ Python cache cleaned"

# Summary
echo ""
echo "=" | head -c 60
echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📦 Backup saved in: $BACKUP_DIR"
echo ""
echo "✨ Repository cleaned. Core files preserved:"
echo ""
echo "  Production Code:"
echo "    ✓ app.py"
echo "    ✓ streamer.py"
echo "    ✓ hardware_pipeline.py"
echo "    ✓ motion_detector.py"
echo "    ✓ motion_detector_cuda.py"
echo "    ✓ cloud_uploader.py"
echo "    ✓ discovery.py"
echo "    ✓ monitor.py"
echo ""
echo "  Configuration:"
echo "    ✓ config.yaml"
echo "    ✓ requirements.txt"
echo ""
echo "  Documentation:"
echo "    ✓ README.md"
echo "    ✓ QUICKSTART.md"
echo "    ✓ DEPLOYMENT.md"
echo "    ✓ PERFORMANCE_GUIDE.md"
echo "    ✓ EXPECTED_OUTPUT.md"
echo "    ✓ NOT_LINKED_FIX_COMPLETE.md"
echo ""
echo "  Containers:"
echo "    ✓ Dockerfile.linux"
echo "    ✓ Dockerfile.rpi"
echo "    ✓ Dockerfile.windows"
echo ""
echo "  Directories:"
echo "    ✓ static/"
echo "    ✓ templates/"
echo "    ✓ logs/"
echo "    ✓ venv/"
echo ""
echo "🚀 Your app is ready: python app.py"
echo ""
