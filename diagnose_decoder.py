#!/usr/bin/env python3
"""
Diagnostic script for hardware decoder issues
Checks GStreamer plugins, decoder capabilities, and RTSP stream compatibility
"""

import subprocess
import sys
import os

def print_section(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def run_command(cmd, description):
    """Run command and return success status and output"""
    print(f"\n{description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✓ SUCCESS")
            if result.stdout:
                print(result.stdout[:500])
            return True, result.stdout
        else:
            print("✗ FAILED")
            if result.stderr:
                print(f"Error: {result.stderr[:500]}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False, ""
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False, str(e)

def check_gstreamer_plugins():
    """Check if NVIDIA decoder plugins are installed"""
    print_section("1. GStreamer NVIDIA Plugins Check")
    
    plugins = [
        'nvv4l2decoder',
        'nvv4l2h264enc',
        'nvvidconv',
        'nvjpegenc',
        'nvarguscamerasrc'
    ]
    
    results = {}
    for plugin in plugins:
        cmd = ['gst-inspect-1.0', plugin]
        success, output = run_command(cmd, f"\nChecking {plugin}...")
        results[plugin] = success
        
        if success and 'decoder' in plugin.lower():
            # Extract supported formats
            if 'Pad Templates' in output:
                print("  Supported input formats:")
                for line in output.split('\n'):
                    if 'stream-format' in line or 'alignment' in line:
                        print(f"    {line.strip()}")
    
    return results

def check_v4l2_devices():
    """Check V4L2 video devices"""
    print_section("2. V4L2 Video Devices")
    
    try:
        # List video devices
        video_devices = []
        for i in range(10):
            device = f"/dev/video{i}"
            if os.path.exists(device):
                video_devices.append(device)
        
        if video_devices:
            print(f"✓ Found {len(video_devices)} video devices:")
            for dev in video_devices:
                print(f"  - {dev}")
                # Try to get device info
                cmd = ['v4l2-ctl', '--device', dev, '--all']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.split('\n')[:5]:
                        if line.strip():
                            print(f"    {line}")
        else:
            print("✗ No video devices found")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Error checking V4L2: {e}")
        return False

def test_decoder_with_file():
    """Test decoder with a local file"""
    print_section("3. Hardware Decoder Test with File")
    
    # First create a test file with hardware encoder
    test_file = "/tmp/decoder_test.h264"
    
    print("\nStep 1: Creating test H.264 file...")
    cmd = [
        'gst-launch-1.0', '-e',
        'videotestsrc', 'num-buffers=100', '!',
        'video/x-raw,width=1280,height=720,framerate=30/1', '!',
        'nvvidconv', '!',
        'nvv4l2h264enc', '!',
        'h264parse', '!',
        'filesink', f'location={test_file}'
    ]
    
    success, _ = run_command(cmd, "Creating test file...")
    
    if not success or not os.path.exists(test_file):
        print("✗ Failed to create test file")
        return False
    
    print(f"✓ Test file created: {test_file}")
    
    # Now test decoder
    print("\nStep 2: Testing hardware decoder...")
    
    # Test 1: Basic decoder test
    cmd = [
        'gst-launch-1.0',
        'filesrc', f'location={test_file}', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'nvvidconv', '!',
        'fakesink'
    ]
    
    success, output = run_command(cmd, "Test 1: Basic decode pipeline")
    
    if not success:
        print("\n⚠ Basic decoder failed. Trying alternative formats...")
        
        # Test 2: Try with explicit caps
        cmd = [
            'gst-launch-1.0',
            'filesrc', f'location={test_file}', '!',
            'h264parse', '!',
            'video/x-h264,stream-format=byte-stream,alignment=au', '!',
            'nvv4l2decoder', '!',
            'fakesink'
        ]
        
        success, output = run_command(cmd, "Test 2: Decode with explicit caps")
    
    return success

def test_decoder_with_rtsp(rtsp_url):
    """Test decoder with RTSP stream"""
    print_section("4. Hardware Decoder Test with RTSP")
    
    print(f"RTSP URL: {rtsp_url}")
    
    # Test 1: Software decode baseline
    print("\n--- Baseline: Software decode ---")
    cmd = [
        'gst-launch-1.0',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'avdec_h264', '!',  # Software decoder
        'fakesink'
    ]
    
    sw_success, _ = run_command(cmd, "Software decoder test (5s)")
    
    # Test 2: Hardware decode
    print("\n--- Hardware decode test ---")
    cmd = [
        'gst-launch-1.0',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'fakesink'
    ]
    
    hw_success, hw_output = run_command(cmd, "Hardware decoder test (5s)")
    
    if not hw_success and sw_success:
        print("\n⚠ Hardware decoder failed but software works")
        print("This suggests the decoder plugin has issues with RTSP stream format")
        
        # Try alternative approaches
        print("\n--- Trying alternative: enable-last-sample=false ---")
        cmd = [
            'gst-launch-1.0',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'video/x-h264,stream-format=byte-stream', '!',
            'nvv4l2decoder', 'enable-max-performance=1', '!',
            'fakesink'
        ]
        
        alt_success, _ = run_command(cmd, "Alternative format test")
        
        return alt_success
    
    return hw_success

def check_decoder_properties():
    """Check nvv4l2decoder properties and capabilities"""
    print_section("5. Hardware Decoder Properties")
    
    cmd = ['gst-inspect-1.0', 'nvv4l2decoder']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Plugin details:")
        
        # Extract important info
        in_properties = False
        for line in result.stdout.split('\n'):
            if 'Element Properties' in line:
                in_properties = True
            if in_properties:
                if line.strip().startswith('enable') or \
                   line.strip().startswith('disable') or \
                   'performance' in line.lower() or \
                   'format' in line.lower():
                    print(f"  {line}")
            
            # Also show pad templates
            if 'Pad Templates' in line:
                print("\n" + line)
            if 'SRC' in line or 'SINK' in line:
                print(f"  {line}")
            if 'stream-format' in line or 'alignment' in line:
                print(f"    {line.strip()}")
        
        return True
    else:
        print("✗ Cannot inspect nvv4l2decoder")
        return False

def suggest_fixes(plugin_results, rtsp_url):
    """Suggest fixes based on diagnostic results"""
    print_section("DIAGNOSIS & FIXES")
    
    if not plugin_results.get('nvv4l2decoder', False):
        print("\n❌ PROBLEM: nvv4l2decoder plugin not found")
        print("\n📋 FIXES:")
        print("   1. Install NVIDIA GStreamer plugins:")
        print("      sudo apt-get install nvidia-l4t-gstreamer")
        print("\n   2. Or on JetPack 4.x:")
        print("      sudo apt-get install gstreamer1.0-plugins-tegra")
        print("\n   3. Verify installation:")
        print("      gst-inspect-1.0 nvv4l2decoder")
        return
    
    print("\n✓ nvv4l2decoder plugin is installed")
    
    print("\n📋 COMMON FIXES FOR DECODER ISSUES:")
    
    print("\n1️⃣  Use FFmpeg with h264_cuvid decoder instead:")
    print("    This often works better than GStreamer nvv4l2decoder")
    print("\n    Python code:")
    print("    ```python")
    print("    cmd = [")
    print("        'ffmpeg', '-rtsp_transport', 'tcp',")
    print(f"        '-i', '{rtsp_url}',")
    print("        '-c:v', 'h264_cuvid',  # NVIDIA CUDA decoder")
    print("        '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1'")
    print("    ]")
    print("    ```")
    
    print("\n2️⃣  Fix stream format compatibility:")
    print("    Add explicit stream-format caps:")
    print("    ```bash")
    print("    gst-launch-1.0 rtspsrc location=... ! \\")
    print("      rtph264depay ! h264parse ! \\")
    print("      video/x-h264,stream-format=byte-stream,alignment=au ! \\")
    print("      nvv4l2decoder enable-max-performance=1 ! \\")
    print("      nvvidconv ! 'video/x-raw,format=BGRx' ! appsink")
    print("    ```")
    
    print("\n3️⃣  Use software decoder as fallback:")
    print("    The application already has this implemented!")
    print("    Check config.yaml:")
    print("    ```yaml")
    print("    use_hardware_decode: true  # Will fallback to software if HW fails")
    print("    ```")
    
    print("\n4️⃣  For Jetson TX2/NX on JetPack 4.x:")
    print("    The hardware decoder may have limited H.264 profile support")
    print("    Check your camera's H.264 settings:")
    print("    - Profile: Baseline or Main (not High)")
    print("    - Level: 4.0 or lower")
    print("    - Resolution: Max 1920x1080")
    
    print("\n5️⃣  Alternative: Use omxh264dec (older Jetson):")
    print("    ```bash")
    print("    gst-launch-1.0 rtspsrc location=... ! \\")
    print("      rtph264depay ! h264parse ! \\")
    print("      omxh264dec ! nvvidconv ! fakesink")
    print("    ```")
    
    print("\n6️⃣  Check system resources:")
    print("    ```bash")
    print("    # Ensure max performance mode")
    print("    sudo nvpmodel -m 0")
    print("    sudo jetson_clocks")
    print("    ")
    print("    # Check decoder allocation")
    print("    sudo cat /sys/kernel/debug/nvmap/iovmm/allocations | grep nvdec")
    print("    ```")

def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║          Hardware Decoder Diagnostic & Fix Script               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # Get RTSP URL
    rtsp_url = "rtsp://admin:tapway123@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0"
    
    if len(sys.argv) > 1:
        rtsp_url = sys.argv[1]
    
    print(f"Testing with RTSP URL: {rtsp_url}")
    
    # Run diagnostics
    plugin_results = check_gstreamer_plugins()
    check_v4l2_devices()
    check_decoder_properties()
    
    if plugin_results.get('nvv4l2decoder', False):
        test_decoder_with_file()
        test_decoder_with_rtsp(rtsp_url)
    
    # Provide fix suggestions
    suggest_fixes(plugin_results, rtsp_url)
    
    print("\n" + "="*70)
    print("Next steps:")
    print("1. Try the suggested fixes above")
    print("2. Test with: python test_hw_acceleration.py")
    print("3. The app will auto-fallback to software decode if HW fails")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
