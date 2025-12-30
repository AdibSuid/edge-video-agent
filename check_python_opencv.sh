#!/bin/bash
# Check Python and OpenCV installation status

echo "=========================================="
echo "Python & OpenCV Diagnostic"
echo "=========================================="
echo ""

# Check Python versions
echo "1. Python Installation:"
echo "   --------------------"
which python3 && python3 --version || echo "   ✗ python3 not found"
which python && python --version 2>/dev/null || echo "   ✗ python not found"

echo ""

# Check pip
echo "2. pip Installation:"
echo "   -----------------"
which pip3 && pip3 --version || echo "   ✗ pip3 not found"
which pip && pip --version 2>/dev/null || echo "   ✗ pip not found"

echo ""

# Try importing cv2
echo "3. OpenCV Import Test:"
echo "   -------------------"
python3 << 'PYEOF'
import sys
print(f"   Python executable: {sys.executable}")
print(f"   Python version: {sys.version}")
print(f"   Python path: {sys.path[0]}")

try:
    import cv2
    print(f"   ✓ OpenCV imported successfully")
    print(f"   OpenCV version: {cv2.__version__}")
    print(f"   OpenCV location: {cv2.__file__}")
except ImportError as e:
    print(f"   ✗ OpenCV import failed: {e}")
    print("")
    print("   OpenCV is NOT installed!")
except Exception as e:
    print(f"   ✗ Error: {e}")
PYEOF

echo ""

# Check installed packages
echo "4. Installed Python Packages (pip):"
echo "   ---------------------------------"
if command -v pip3 &> /dev/null; then
    pip3 list | grep -i opencv | sed 's/^/   /' || echo "   No OpenCV packages found"
else
    echo "   pip3 not available"
fi

echo ""

# Check for system OpenCV
echo "5. System OpenCV (JetPack pre-installed):"
echo "   ---------------------------------------"
find /usr -name "cv2*.so" 2>/dev/null | sed 's/^/   /' || echo "   Not found in /usr"

# Check common Python paths
echo ""
echo "   Checking Python site-packages:"
python3 -c "import site; print('\n'.join(['   ' + p for p in site.getsitepackages()]))" 2>/dev/null

echo ""
for sitedir in $(python3 -c "import site; print(' '.join(site.getsitepackages()))" 2>/dev/null); do
    if [ -d "$sitedir" ]; then
        echo "   Contents of $sitedir:"
        ls -la "$sitedir" | grep -i cv | sed 's/^/     /' || echo "     No cv2 found"
    fi
done

echo ""

# Check for virtual environment
echo "6. Virtual Environment Check:"
echo "   --------------------------"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "   ✓ Virtual environment active: $VIRTUAL_ENV"
else
    echo "   ✗ No virtual environment active"
fi

if [ -d "venv" ] || [ -d ".venv" ] || [ -d "env" ]; then
    echo "   ⚠ Virtual environment directory found in current folder"
    echo "     You may need to activate it:"
    echo "     source venv/bin/activate  # or .venv/bin/activate"
fi

echo ""

# Check if cv2.so is in Python path
echo "7. Detailed cv2 Search:"
echo "   --------------------"
python3 << 'PYEOF'
import sys
import os

print("   Searching for cv2 in Python paths:")
for path in sys.path:
    if os.path.isdir(path):
        for item in os.listdir(path):
            if 'cv2' in item.lower():
                full_path = os.path.join(path, item)
                print(f"     Found: {full_path}")
PYEOF

echo ""

# Summary
echo "=========================================="
echo "DIAGNOSIS & RECOMMENDATIONS"
echo "=========================================="
echo ""

# Try to import and determine the issue
python3 << 'PYEOF'
import sys

try:
    import cv2
    print("✓ OpenCV is installed and working")
    print("")

    # Check GStreamer support
    build_info = cv2.getBuildInformation()
    if 'GStreamer' in build_info:
        if 'YES' in build_info.split('GStreamer')[1].split('\n')[0]:
            print("✓ OpenCV has GStreamer support: YES")
            print("")
            print("You don't need to rebuild OpenCV!")
            print("Your system is ready for hardware acceleration.")
        else:
            print("⚠ OpenCV has GStreamer support: NO")
            print("")
            print("OpenCV is installed but doesn't have GStreamer support.")
            print("")
            print("Options:")
            print("  1. Rebuild OpenCV with GStreamer (see rebuild_opencv_tx2.sh)")
            print("  2. Use GStreamer subprocess for both encode and decode")
            print("     (no OpenCV rebuild needed)")
    else:
        print("⚠ Could not determine GStreamer support from build info")

except ImportError:
    print("✗ OpenCV is NOT installed")
    print("")
    print("You need to install OpenCV. Choose one:")
    print("")
    print("Option 1: Install from pip (quick, no GStreamer support)")
    print("  pip3 install opencv-python")
    print("  - Pros: Fast (2 minutes)")
    print("  - Cons: No GStreamer support, decode won't use hardware")
    print("")
    print("Option 2: Use JetPack pre-installed OpenCV (if available)")
    print("  - Check if it exists: find /usr -name 'cv2*.so'")
    print("  - May need to add to PYTHONPATH")
    print("")
    print("Option 3: Build from source (slow, full GStreamer support)")
    print("  ./rebuild_opencv_tx2.sh")
    print("  - Pros: Full GStreamer support, hardware decode and encode")
    print("  - Cons: Takes ~2 hours")
    print("")
    print("Recommendation for fastest results:")
    print("  1. Install opencv-python: pip3 install opencv-python")
    print("  2. Test your app - encoding will work (uses GStreamer subprocess)")
    print("  3. If decode fails, update decode code to use GStreamer subprocess")
    print("  4. This way you get hardware acceleration without 2-hour build")

except Exception as e:
    print(f"✗ Error checking OpenCV: {e}")
PYEOF

echo ""
