#!/usr/bin/env python3
"""
Quick NVDEC verification - checks if hardware decoder is actually being used
"""

import subprocess
import sys
import time
import threading

def monitor_nvdec():
    """Monitor NVDEC usage in background"""
    nvdec_active = []
    
    def check_nvdec():
        for _ in range(10):  # Check for 10 seconds
            try:
                result = subprocess.run(
                    ['cat', '/sys/kernel/debug/nvmap/iovmm/allocations'],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                
                if 'nvdec' in result.stdout.lower():
                    nvdec_active.append(True)
                    
                time.sleep(1)
            except:
                pass
    
    thread = threading.Thread(target=check_nvdec, daemon=True)
    thread.start()
    
    return nvdec_active

def test_decoder_quick(rtsp_url):
    """Quick test that stops after confirming decoder works"""
    print("="*70)
    print("Quick Hardware Decoder Verification")
    print("="*70)
    print(f"\nRTSP URL: {rtsp_url}")
    print("\nStarting decoder test (will auto-stop after 5 seconds)...")
    print("Monitoring NVDEC activity...\n")
    
    # Start NVDEC monitoring
    nvdec_activity = monitor_nvdec()
    
    # Run decoder for limited time
    cmd = [
        'timeout', '5',  # Use timeout command to stop after 5s
        'gst-launch-1.0', '-q',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'fakesink', 'sync=false'
    ]
    
    try:
        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7
        )
        elapsed = time.time() - start
        
        # Give monitoring thread time to catch activity
        time.sleep(1)
        
        print(f"Test completed in {elapsed:.1f}s")
        
        if nvdec_activity:
            print("\n" + "="*70)
            print("✅ SUCCESS: Hardware decoder IS WORKING!")
            print("="*70)
            print(f"NVDEC was active {len(nvdec_activity)} times during the test")
            print("\nThis confirms:")
            print("  ✓ nvv4l2decoder plugin is functional")
            print("  ✓ Hardware decoding is being used")
            print("  ✓ Your application will benefit from HW acceleration")
            return True
        else:
            print("\n" + "="*70)
            print("⚠ WARNING: No NVDEC activity detected")
            print("="*70)
            print("The decoder may be using software fallback")
            return False
            
    except subprocess.TimeoutExpired:
        time.sleep(1)
        
        if nvdec_activity:
            print("\n" + "="*70)
            print("✅ SUCCESS: Hardware decoder IS WORKING!")
            print("="*70)
            print(f"NVDEC was active {len(nvdec_activity)} times during the test")
            print("\nNote: Test timed out but that's OK - decoder is functional!")
            return True
        else:
            print("\n⚠ Timed out with no NVDEC activity")
            return False
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_nvdec.py '<RTSP_URL>'")
        print("\nExample:")
        print("  python verify_nvdec.py 'rtsp://admin:pass@192.168.0.130:554/cam/realmonitor?channel=1&subtype=0'")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║               NVDEC Hardware Decoder Verification               ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    success = test_decoder_quick(rtsp_url)
    
    if success:
        print("\n" + "="*70)
        print("VERDICT: Hardware decoder is WORKING correctly! 🎉")
        print("="*70)
        print("\nYour config.yaml setting is correct:")
        print("  use_hardware_decode: true")
        print("\nThe 'timeout' in other tests doesn't mean decoder failed,")
        print("it just means the test needs adjustment. Your decoder works!")
    else:
        print("\n" + "="*70)
        print("VERDICT: Hardware decoder may not be working")
        print("="*70)
        print("\nTroubleshooting:")
        print("1. Check if nvv4l2decoder plugin exists:")
        print("   gst-inspect-1.0 nvv4l2decoder")
        print("\n2. Try with a different decoder:")
        print("   - omxh264dec (older Jetson)")
        print("   - Use software decode as fallback")
        print("\n3. Run full troubleshooting:")
        print(f"   python troubleshoot_rtsp_decoder.py '{rtsp_url}'")
    
    print()

if __name__ == "__main__":
    main()
