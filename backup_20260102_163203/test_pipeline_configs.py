#!/usr/bin/env python3
"""
Test different GStreamer pipeline configurations to find what works
"""

import subprocess
import sys

def test_pipeline(name, cmd, timeout=10):
    """Test a pipeline configuration"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            print(f"✓ SUCCESS")
            return True
        else:
            print(f"✗ FAILED - Return code: {result.returncode}")
            if result.stderr:
                # Show relevant errors
                for line in result.stderr.split('\n'):
                    if 'error' in line.lower() or 'failed' in line.lower() or 'not-linked' in line.lower():
                        print(f"  {line.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT after {timeout}s")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_pipeline_configs.py '<RTSP_URL>'")
        sys.exit(1)
    
    rtsp_url = sys.argv[1]
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║        GStreamer Pipeline Configuration Tester                   ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    print(f"\nRTSP URL: {rtsp_url}")
    print("Testing different pipeline configurations...\n")
    
    configs = [
        # Test 1: Basic hardware decoder without conversion
        ("Hardware decoder - no conversion", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'nvv4l2decoder', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 2: Hardware decoder with nvvidconv (NVMM memory)
        ("Hardware decoder + nvvidconv", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'nvv4l2decoder', '!',
            'nvvidconv', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 3: Hardware decoder with explicit output format
        ("Hardware decoder + explicit caps", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'nvv4l2decoder', '!',
            'video/x-raw(memory:NVMM)', '!',
            'nvvidconv', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 4: Hardware decoder with BGRx output
        ("Hardware decoder + BGRx", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'nvv4l2decoder', '!',
            'nvvidconv', '!',
            'video/x-raw,format=BGRx', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 5: Hardware decoder with I420 format
        ("Hardware decoder + I420", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'nvv4l2decoder', '!',
            'nvvidconv', '!',
            'video/x-raw,format=I420', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 6: OMX decoder (older Jetson)
        ("OMX decoder", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'omxh264dec', '!',
            'nvvidconv', '!',
            'fakesink', 'sync=false'
        ]),
        
        # Test 7: Software decoder (baseline)
        ("Software decoder", [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={rtsp_url}', 'latency=200', 'num-buffers=50', '!',
            'rtph264depay', '!',
            'h264parse', '!',
            'avdec_h264', '!',
            'videoconvert', '!',
            'fakesink', 'sync=false'
        ]),
    ]
    
    results = {}
    
    for name, cmd in configs:
        success = test_pipeline(name, cmd)
        results[name] = success
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    working = []
    failed = []
    
    for name, success in results.items():
        status = "✓ WORKS" if success else "✗ FAILED"
        print(f"{name:40s}: {status}")
        if success:
            working.append(name)
        else:
            failed.append(name)
    
    # Recommendation
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    if working:
        print(f"\n✓ Found {len(working)} working configuration(s)!")
        print(f"\nBest option: {working[0]}")
        
        # Show the working pipeline
        for name, cmd in configs:
            if name == working[0]:
                print("\nWorking pipeline:")
                print("```")
                pipeline_str = ' '.join(cmd)
                # Format nicely
                pipeline_str = pipeline_str.replace('gst-launch-1.0 -e ', '')
                pipeline_str = pipeline_str.replace(' ! ', ' \\\n  ! ')
                print(pipeline_str)
                print("```")
                break
        
        # Hardware decoder verdict
        if any('Hardware' in w for w in working):
            print("\n🎉 Hardware decoder IS WORKING!")
            print("   Use this configuration in your application")
        else:
            print("\n⚠ Only software decoder works")
            print("   Hardware decoder may have issues with this stream")
    else:
        print("\n✗ No working configurations found!")
        print("\nTroubleshooting:")
        print("1. Check RTSP stream is accessible:")
        print(f"   ffplay {rtsp_url}")
        print("\n2. Check GStreamer plugins:")
        print("   gst-inspect-1.0 nvv4l2decoder")
        print("   gst-inspect-1.0 nvvidconv")
        print("\n3. Check camera H.264 settings:")
        print("   - Profile: Baseline or Main (not High)")
        print("   - Resolution: ≤1920x1080")
    
    print()

if __name__ == "__main__":
    main()
