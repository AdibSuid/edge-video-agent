python3 << 'EOF'
import cv2

print("=" * 60)
print(f"OpenCV Version: {cv2.__version__}")
print("=" * 60)

build_info = cv2.getBuildInformation()

# Extract GStreamer section
if "GStreamer" in build_info:
    lines = build_info.split('\n')
    in_video_section = False
    for line in lines:
        if "Video I/O:" in line:
            in_video_section = True
        if in_video_section:
            print(line)
            if "GStreamer" in line:
                if "YES" in line:
                    print("\n✓ GStreamer is ENABLED")
                else:
                    print("\n✗ GStreamer is DISABLED")
                break
        if in_video_section and line.strip() == "":
            break
else:
    print("✗ GStreamer information not found in build")
EOF