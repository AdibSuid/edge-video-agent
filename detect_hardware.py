#!/usr/bin/env python3
"""
Hardware detection and optimization tool for edge-video-agent
Detects Jetson Orin, Raspberry Pi, or generic x86 platforms
"""

import subprocess
import sys
import os
import json
from pathlib import Path


def detect_platform():
    """Detect hardware platform"""
    platform_info = {
        'platform': 'unknown',
        'model': 'unknown',
        'cuda_available': False,
        'cuda_devices': 0,
        'opencv_version': None,
        'opencv_cuda': False,
        'ffmpeg_nvenc': False,
        'ffmpeg_cuvid': False,
        'recommended_streams': 2,
        'optimizations': []
    }
    
    # Check for Jetson
    if os.path.exists('/etc/nv_tegra_release'):
        platform_info['platform'] = 'jetson'
        try:
            with open('/etc/nv_tegra_release', 'r') as f:
                content = f.read()
                if 'Orin' in content:
                    if 'Nano' in content:
                        platform_info['model'] = 'Jetson Orin Nano'
                    else:
                        platform_info['model'] = 'Jetson Orin'
                    platform_info['recommended_streams'] = 8
                else:
                    platform_info['model'] = 'Jetson (Unknown)'
                    platform_info['recommended_streams'] = 4
        except:
            platform_info['model'] = 'Jetson (Unknown)'
            
    # Check for Raspberry Pi
    elif os.path.exists('/proc/device-tree/model'):
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip('\x00')
                if 'Raspberry Pi' in model:
                    platform_info['platform'] = 'raspberry-pi'
                    platform_info['model'] = model
                    if '5' in model:
                        platform_info['recommended_streams'] = 3
                    else:
                        platform_info['recommended_streams'] = 2
        except:
            pass
    else:
        platform_info['platform'] = 'x86'
        platform_info['model'] = 'Generic x86/x64'
        platform_info['recommended_streams'] = 5
    
    return platform_info


def check_opencv():
    """Check OpenCV installation and CUDA support"""
    try:
        import cv2
        version = cv2.__version__
        cuda_devices = 0
        cuda_available = False
        
        try:
            cuda_devices = cv2.cuda.getCudaEnabledDeviceCount()
            cuda_available = cuda_devices > 0
        except:
            pass
        
        return {
            'installed': True,
            'version': version,
            'cuda_available': cuda_available,
            'cuda_devices': cuda_devices
        }
    except ImportError:
        return {
            'installed': False,
            'version': None,
            'cuda_available': False,
            'cuda_devices': 0
        }


def check_ffmpeg():
    """Check FFmpeg capabilities"""
    info = {
        'installed': False,
        'version': None,
        'nvenc': False,
        'cuvid': False,
        'v4l2m2m': False
    }
    
    try:
        # Check if ffmpeg is installed
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info['installed'] = True
            lines = result.stdout.split('\n')
            if lines:
                info['version'] = lines[0]
        
        # Check for encoders
        result = subprocess.run(['ffmpeg', '-encoders'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout
            info['nvenc'] = 'h264_nvenc' in output
            info['v4l2m2m'] = 'h264_v4l2m2m' in output
        
        # Check for decoders
        result = subprocess.run(['ffmpeg', '-decoders'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout
            info['cuvid'] = 'h264_cuvid' in output
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return info


def get_recommendations(platform_info, opencv_info, ffmpeg_info):
    """Generate optimization recommendations"""
    recommendations = []
    config_updates = {}
    
    # Platform-specific recommendations
    if platform_info['platform'] == 'jetson':
        if opencv_info['cuda_available']:
            recommendations.append("✓ CUDA-accelerated motion detection available")
            config_updates['use_cuda_motion_detection'] = True
        else:
            recommendations.append("⚠ OpenCV CUDA support not detected - rebuild OpenCV with CUDA")
            config_updates['use_cuda_motion_detection'] = False
        
        if ffmpeg_info['nvenc'] and ffmpeg_info['cuvid']:
            recommendations.append("✓ NVENC/NVDEC hardware encoding available")
            config_updates['use_hardware_decode'] = True
            config_updates['use_hardware_encode'] = True
        else:
            recommendations.append("⚠ NVENC/NVDEC not available - install proper FFmpeg")
            
        recommendations.append(f"✓ Can handle up to {platform_info['recommended_streams']} concurrent streams")
        config_updates['motion_detection_scale'] = 0.25
        config_updates['motion_frame_skip'] = 2
        
    elif platform_info['platform'] == 'raspberry-pi':
        recommendations.append("• Raspberry Pi detected - using CPU optimizations")
        config_updates['use_cuda_motion_detection'] = False
        config_updates['use_hardware_decode'] = True
        
        if ffmpeg_info['v4l2m2m']:
            recommendations.append("✓ V4L2 hardware encoding available")
            config_updates['use_hardware_encode'] = True
        
        recommendations.append(f"• Recommended max streams: {platform_info['recommended_streams']}")
        config_updates['motion_detection_scale'] = 0.2
        config_updates['motion_frame_skip'] = 3
        
    else:
        recommendations.append("• Generic platform detected")
        if opencv_info['cuda_available']:
            recommendations.append("✓ CUDA support available")
            config_updates['use_cuda_motion_detection'] = True
        else:
            recommendations.append("• No CUDA support - using CPU")
            config_updates['use_cuda_motion_detection'] = False
        
        config_updates['use_hardware_decode'] = False
        config_updates['motion_detection_scale'] = 0.25
        config_updates['motion_frame_skip'] = 2
    
    # General recommendations
    if not ffmpeg_info['installed']:
        recommendations.append("⚠ FFmpeg not installed - install it for video processing")
    
    if not opencv_info['installed']:
        recommendations.append("⚠ OpenCV not installed - install opencv-python or build from source")
    
    return recommendations, config_updates


def print_report(platform_info, opencv_info, ffmpeg_info, recommendations, config_updates):
    """Print detailed hardware report"""
    print("=" * 70)
    print("  EDGE VIDEO AGENT - Hardware Detection Report")
    print("=" * 70)
    print()
    
    print("Platform Information:")
    print(f"  Platform: {platform_info['platform']}")
    print(f"  Model: {platform_info['model']}")
    print(f"  Recommended Streams: {platform_info['recommended_streams']}")
    print()
    
    print("OpenCV Status:")
    if opencv_info['installed']:
        print(f"  Version: {opencv_info['version']}")
        print(f"  CUDA Support: {'Yes' if opencv_info['cuda_available'] else 'No'}")
        if opencv_info['cuda_available']:
            print(f"  CUDA Devices: {opencv_info['cuda_devices']}")
    else:
        print("  Status: Not installed")
    print()
    
    print("FFmpeg Status:")
    if ffmpeg_info['installed']:
        print(f"  Version: {ffmpeg_info['version']}")
        print(f"  NVENC Support: {'Yes' if ffmpeg_info['nvenc'] else 'No'}")
        print(f"  CUVID/NVDEC Support: {'Yes' if ffmpeg_info['cuvid'] else 'No'}")
        print(f"  V4L2M2M Support: {'Yes' if ffmpeg_info['v4l2m2m'] else 'No'}")
    else:
        print("  Status: Not installed")
    print()
    
    print("Recommendations:")
    for rec in recommendations:
        print(f"  {rec}")
    print()
    
    print("Suggested Configuration Updates:")
    for key, value in config_updates.items():
        print(f"  {key}: {value}")
    print()
    
    print("=" * 70)
    
    return config_updates


def update_config_file(config_updates):
    """Update config.yaml with optimizations"""
    import yaml
    
    config_file = Path('config.yaml')
    
    if not config_file.exists():
        print("Warning: config.yaml not found")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Update config
        config.update(config_updates)
        
        # Backup original
        backup_file = Path('config.yaml.backup')
        if not backup_file.exists():
            with open(backup_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            print(f"Backup created: {backup_file}")
        
        # Write updated config
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"Configuration updated: {config_file}")
        return True
        
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


def main():
    """Main function"""
    print("\nDetecting hardware...\n")
    
    # Detect platform
    platform_info = detect_platform()
    
    # Check OpenCV
    opencv_info = check_opencv()
    
    # Check FFmpeg
    ffmpeg_info = check_ffmpeg()
    
    # Get recommendations
    recommendations, config_updates = get_recommendations(
        platform_info, opencv_info, ffmpeg_info
    )
    
    # Print report
    config_updates = print_report(
        platform_info, opencv_info, ffmpeg_info, 
        recommendations, config_updates
    )
    
    # Ask to update config
    if config_updates:
        response = input("\nUpdate config.yaml with recommended settings? [y/N]: ")
        if response.lower() == 'y':
            if update_config_file(config_updates):
                print("✓ Configuration updated successfully")
            else:
                print("✗ Failed to update configuration")
        else:
            print("Configuration not updated")
    
    # Export JSON report
    report = {
        'platform': platform_info,
        'opencv': opencv_info,
        'ffmpeg': ffmpeg_info,
        'recommendations': recommendations,
        'config_updates': config_updates
    }
    
    report_file = Path('hardware_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {report_file}")


if __name__ == '__main__':
    main()
