"""
JetPack version detection and hardware acceleration utilities
Supports both JetPack 4 (TX2, Xavier) and JetPack 5 (Orin series)
"""

import os
import re
import subprocess
from typing import Optional, Tuple


def get_jetpack_version() -> Tuple[Optional[int], Optional[int]]:
    """
    Detect JetPack major and minor version.

    Returns:
        Tuple of (major, minor) version numbers, or (None, None) if not a Jetson

    Examples:
        - JetPack 4.6.1 returns (4, 6)
        - JetPack 5.1.2 returns (5, 1)
    """
    if not os.path.exists('/etc/nv_tegra_release'):
        return None, None

    try:
        # Try to get L4T version from dpkg
        result = subprocess.run(
            ['dpkg', '-l', 'nvidia-l4t-core'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Parse L4T version
            # L4T 32.x = JetPack 4.x
            # L4T 35.x = JetPack 5.x
            match = re.search(r'nvidia-l4t-core\s+(\d+)\.(\d+)', result.stdout)
            if match:
                l4t_major = int(match.group(1))
                l4t_minor = int(match.group(2))

                # Convert L4T to JetPack version
                if l4t_major == 32:
                    # L4T 32.x = JetPack 4.x
                    # Map L4T 32.6.x -> JP 4.6
                    return 4, l4t_minor
                elif l4t_major == 35:
                    # L4T 35.x = JetPack 5.x
                    # Map L4T 35.1 -> JP 5.0, 35.2 -> JP 5.1, etc
                    jp_minor = max(0, l4t_minor - 1)
                    return 5, jp_minor
                elif l4t_major == 36:
                    # L4T 36.x = JetPack 6.x
                    return 6, 0

        # Fallback: parse /etc/nv_tegra_release
        with open('/etc/nv_tegra_release', 'r') as f:
            content = f.read()
            # Look for "R32" (JP4) or "R35" (JP5)
            match = re.search(r'R(\d+)\s+\(release\)', content)
            if match:
                r_version = int(match.group(1))
                if r_version == 32:
                    return 4, 6  # Default to 4.6
                elif r_version == 35:
                    return 5, 1  # Default to 5.1
                elif r_version == 36:
                    return 6, 0

    except Exception:
        pass

    return None, None


def get_hardware_config():
    """
    Get hardware-specific configuration for video encode/decode.

    Returns:
        dict with keys:
            - gstreamer_decoder: GStreamer decoder element name
            - gstreamer_encoder: GStreamer encoder element name
            - ffmpeg_decoder: FFmpeg decoder codec name
            - ffmpeg_encoder: FFmpeg encoder codec name (preferred)
            - ffmpeg_encoder_fallback: FFmpeg encoder fallback
            - jetpack_version: (major, minor) tuple
    """
    jp_major, jp_minor = get_jetpack_version()

    config = {
        'jetpack_version': (jp_major, jp_minor),
        'jetpack_major': jp_major,
        'jetpack_minor': jp_minor,
    }

    if jp_major == 4:
        # JetPack 4.x (TX2, Xavier) - Uses V4L2 (OMX deprecated since JP 4.2)
        # NVIDIA Official: "gst-omx is deprecated, use gst-v4l2 instead"
        config.update({
            'gstreamer_decoder': 'nvv4l2decoder',  # Community standard (NOT omxh264dec)
            'gstreamer_encoder': 'nvv4l2h264enc',  # Community standard (NOT omxh264enc)
            'use_gstreamer': True,  # Use GStreamer, NOT FFmpeg
            'api_type': 'v4l2',
            # Legacy OMX (deprecated, only for fallback)
            'legacy_decoder': 'omxh264dec',
            'legacy_encoder': 'omxh264enc',
        })
    elif jp_major == 5:
        # JetPack 5.x (Orin series) - Uses V4L2
        config.update({
            'gstreamer_decoder': 'nvv4l2decoder',
            'gstreamer_encoder': 'nvv4l2h264enc',
            'use_gstreamer': True,  # Use GStreamer, NOT FFmpeg
            'api_type': 'v4l2',
        })
    elif jp_major == 6:
        # JetPack 6.x - Same as JP5
        config.update({
            'gstreamer_decoder': 'nvv4l2decoder',
            'gstreamer_encoder': 'nvv4l2h264enc',
            'use_gstreamer': True,  # Use GStreamer, NOT FFmpeg
            'api_type': 'v4l2',
        })
    else:
        # Unknown or non-Jetson - Use software encoding
        config.update({
            'gstreamer_decoder': None,
            'gstreamer_encoder': None,
            'use_gstreamer': False,
            'api_type': 'software'
        })

    return config


def check_encoder_available(encoder_name: str) -> bool:
    """
    Check if a specific FFmpeg encoder is available.

    Args:
        encoder_name: Encoder codec name (e.g., 'h264_nvenc', 'h264_omx')

    Returns:
        True if encoder is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return encoder_name in result.stdout
    except Exception:
        return False


def check_decoder_available(decoder_name: str) -> bool:
    """
    Check if a specific FFmpeg decoder is available.

    Args:
        decoder_name: Decoder codec name (e.g., 'h264_cuvid')

    Returns:
        True if decoder is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-decoders'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return decoder_name in result.stdout
    except Exception:
        return False


def check_gstreamer_element(element_name: str) -> bool:
    """
    Check if a GStreamer element is available.

    Args:
        element_name: Element name (e.g., 'omxh264dec', 'nvv4l2decoder')

    Returns:
        True if element is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['gst-inspect-1.0', element_name],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


if __name__ == '__main__':
    # Test detection
    jp_major, jp_minor = get_jetpack_version()
    print(f"JetPack Version: {jp_major}.{jp_minor if jp_minor else 'x'}")

    config = get_hardware_config()
    print(f"\nHardware Configuration:")
    print(f"  API Type: {config['api_type']}")
    print(f"  GStreamer Decoder: {config['gstreamer_decoder']}")
    print(f"  GStreamer Encoder: {config['gstreamer_encoder']}")
    print(f"  FFmpeg Decoder: {config['ffmpeg_decoder']}")
    print(f"  FFmpeg Encoder: {config['ffmpeg_encoder']}")
    print(f"  FFmpeg Encoder Fallback: {config['ffmpeg_encoder_fallback']}")

    # Check availability
    print(f"\nAvailability Check:")
    if config['gstreamer_decoder']:
        available = check_gstreamer_element(config['gstreamer_decoder'])
        print(f"  {config['gstreamer_decoder']}: {'✓' if available else '✗'}")

    if config['ffmpeg_encoder']:
        available = check_encoder_available(config['ffmpeg_encoder'])
        print(f"  {config['ffmpeg_encoder']}: {'✓' if available else '✗'}")

    if config['ffmpeg_encoder_fallback'] != config['ffmpeg_encoder']:
        available = check_encoder_available(config['ffmpeg_encoder_fallback'])
        print(f"  {config['ffmpeg_encoder_fallback']}: {'✓' if available else '✗'}")
