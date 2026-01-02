#!/usr/bin/env python3
"""
Run hardware decoder long enough to see NVDEC activity in jtop
This will decode continuously so you can monitor with jtop in another terminal
"""

import subprocess
import sys
import time

def run_continuous_decode(rtsp_url, duration=30):
    """
    Run hardware decoder for a specified duration
    This gives you time to see NVDEC in jtop
    """
    
    print("="*70)
    print("Continuous Hardware Decoder Test")
    print("="*70)
    print(f"\nRTSP URL: {rtsp_url}")
    print(f"Duration: {duration} seconds")
    print("\n⚠️  IMPORTANT: Open another terminal and run 'jtop' NOW!")
    print("    Watch the NVDEC section while this runs...\n")
    
    input("Press Enter when jtop is ready...")
    
    print(f"\nStarting hardware decoder for {duration} seconds...")
    print("Watch NVDEC in jtop - you should see activity!\n")
    
    # Pipeline that will run continuously
    cmd = [
        'gst-launch-1.0', '-q',
        'rtspsrc', f'location={rtsp_url}', 'latency=200', '!',
        'rtph264depay', '!',
        'h264parse', '!',
        'nvv4l2decoder', '!',
        'nvvidconv', '!',
        'video/x-raw,format=BGRx', '!',
        'fakesink', 'sync=false'
    ]
    
    try:
        print("Decoder running... (checking NVDEC)")
        
        # Run with timeout
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Monitor for specified duration
        start_time = time.time()
        while time.time() - start_time < duration:
            remaining = int(duration - (time.time() - start_time))
            print(f"\rTime remaining: {remaining}s - Check NVDEC in jtop now!", end='', flush=True)
            time.sleep(1)
            
            # Check if process died
            if proc.poll() is not None:
                print("\n\n⚠️  Process ended early!")
                stdout, stderr = proc.communicate()
                if stderr:
                    print(f"Error: {stderr.decode('utf-8')[:300]}")
                return False
        
        print("\n\nStopping decoder...")
        proc.terminate()
        
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        
        print("\n" + "="*70)
        print("✓ Test completed!")
        print("="*70)
        print("\nDid you see NVDEC activity in jtop?")
        print("  YES → Hardware decoder is working! ✅")
        print("  NO  → Hardware decoder may not be working ❌")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        proc.terminate()
        proc.wait()
        return False
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        return False

def run_comparison_test(rtsp_url):
    """
    Compare hardware vs software decoder side by side
    """
    print("\n" + "="*70)
    print("COMPARISON: Hardware vs Software Decoder")
    print("="*70)
    
    tests = [
        ("Hardware (nvv4l2decoder)", [
            'gst-launch-1.0', '-q',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=300', '!',
            'rtph264depay', '!', 'h264parse', '!',
            'nvv4l2decoder', '!',
            'nvvidconv', '!',
            'video/x-raw,format=BGRx', '!',
            'fakesink', 'sync=false'
        ]),
        ("Software (avdec_h264)", [
            'gst-launch-1.0', '-q',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=300', '!',
            'rtph264depay', '!', 'h264parse', '!',
            'avdec_h264', '!',
            'videoconvert', '!',
            'fakesink', 'sync=false'
        ])
    ]
    
    for name, cmd in tests:
        print(f"\nTesting: {name}")
        print("Watch jtop for NVDEC (hardware) or CPU usage (software)...")
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, timeout=20)
        elapsed = time.time() - start
        
        if result.returncode == 0:
            print(f"  ✓ Completed in {elapsed:.2f}s")
        else:
            print(f"  ✗ Failed")
        
        time.sleep(2)  # Pause between tests

def check_nvdec_allocation():
    """Check if NVDEC is allocated in the system"""
    print("\n" + "="*70)
    print("Checking NVDEC Allocation")
    print("="*70)
    
    try:
        result = subprocess.run(
            ['cat', '/sys/kernel/debug/nvmap/iovmm/allocations'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if 'nvdec' in result.stdout.lower():
            lines = [l for l in result.stdout.split('\n') if 'nvdec' in l.lower()]
            print(f"\n✓ Found {len(lines)} NVDEC allocation(s):")
            for line in lines[:5]:  # Show first 5
                print(f"  {line.strip()}")
            return True
        else:
            print("\n✗ No NVDEC allocations found")
            return False
            
    except Exception as e:
        print(f"\n⚠️  Could not check allocations: {e}")
        print("  Try running with: sudo python script.py")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python watch_nvdec.py '<RTSP_URL>' [duration]")
        print("\nExample:")
        print("  python watch_nvdec.py 'rtsp://admin:pass@ip:554/path?channel=1&subtype=0' 30")
        print("\nThis will run the decoder long enough to see NVDEC in jtop")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           Hardware Decoder - NVDEC Activity Monitor             ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    print("\nThis script will:")
    print("1. Run hardware decoder continuously")
    print("2. Give you time to observe NVDEC in jtop")
    print("3. Check NVDEC allocations\n")
    
    # Run continuous decode
    success = run_continuous_decode(rtsp_url, duration)
    
    if success:
        # Check allocations after test
        time.sleep(2)
        check_nvdec_allocation()
    
    # Optionally run comparison
    print("\n" + "="*70)
    response = input("\nRun hardware vs software comparison? (y/n): ").strip().lower()
    if response == 'y':
        run_comparison_test(rtsp_url)
    
    print("\n" + "="*70)
    print("Tips for monitoring:")
    print("  - Run 'jtop' in another terminal")
    print("  - Look at the NVDEC row (should show percentage)")
    print("  - Hardware decoder = NVDEC active, low CPU")
    print("  - Software decoder = No NVDEC, high CPU")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
