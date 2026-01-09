#!/usr/bin/env python3
"""
RTSP Relay Manager
Manages RTSP re-streaming using FFmpeg to make local cameras accessible to cloud DeepStream
"""

import subprocess
import time
import threading
import logging
from pathlib import Path

class RTSPRelayManager:
    """
    Manage RTSP relay for cloud access using FFmpeg

    This creates FFmpeg processes that:
    1. Pull RTSP from local cameras
    2. Push RTSP to MediaMTX relay server
    3. Make streams accessible via public IP/domain
    """

    def __init__(self, config):
        self.config = config
        self.relay_port = config.get('rtsp_relay_port', 8554)
        self.public_ip = config.get('edge_public_ip', '')
        self.public_domain = config.get('edge_public_domain', '')
        self.relays = {}  # stream_id -> relay process
        self.logger = self._setup_logger()

        # Check if MediaMTX is required
        if not self.public_ip and not self.public_domain:
            self.logger.warning("WARNING: No edge_public_ip or edge_public_domain configured!")
            self.logger.warning("WARNING: DeepStream will not be able to access streams from cloud")
            self.logger.warning("WARNING: Add 'edge_public_ip' or 'edge_public_domain' to config.yaml")

    def _setup_logger(self):
        logger = logging.getLogger('rtsp-relay')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - RTSP Relay - %(message)s'))
            logger.addHandler(handler)
        return logger

    def get_public_rtsp_url(self, stream_id):
        """
        Generate public RTSP URL for a stream
        Returns the URL that DeepStream can access
        """
        if self.public_domain:
            base = self.public_domain
        elif self.public_ip:
            base = self.public_ip
        else:
            # Fallback - won't work from cloud
            self.logger.warning(f"No public IP/domain - using localhost for {stream_id}")
            base = "localhost"

        return f"rtsp://{base}:{self.relay_port}/{stream_id}"

    def start_relay(self, stream_id, source_rtsp_url):
        """
        Start RTSP relay for a stream using FFmpeg

        FFmpeg pulls from local camera and pushes to MediaMTX relay server
        which then makes it accessible via public IP
        """
        if stream_id in self.relays:
            self.logger.info(f"Relay already running for {stream_id}")
            return True

        try:
            # FFmpeg pushes to MediaMTX server running on localhost
            relay_output = f"rtsp://127.0.0.1:{self.relay_port}/{stream_id}"

            # FFmpeg command for RTSP relay (copy codec for efficiency)
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', source_rtsp_url,  # Input: local camera RTSP
                '-c', 'copy',  # Copy codec (no re-encoding)
                '-f', 'rtsp',  # Output format: RTSP
                '-rtsp_transport', 'tcp',
                relay_output  # Output: MediaMTX relay server
            ]

            self.logger.info(f"Starting RTSP relay: {stream_id}")
            self.logger.info(f"  Local source: {source_rtsp_url[:30]}...")
            self.logger.info(f"  Public access: {self.get_public_rtsp_url(stream_id)}")

            # Start FFmpeg relay process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )

            self.relays[stream_id] = {
                'process': process,
                'source_url': source_rtsp_url,
                'public_url': self.get_public_rtsp_url(stream_id)
            }

            self.logger.info(f"OK: RTSP relay started for {stream_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start RTSP relay for {stream_id}: {e}")
            return False

    def stop_relay(self, stream_id):
        """Stop RTSP relay for a stream"""
        if stream_id in self.relays:
            try:
                relay_info = self.relays[stream_id]
                process = relay_info['process']

                process.terminate()
                process.wait(timeout=5)

                del self.relays[stream_id]
                self.logger.info(f"OK: RTSP relay stopped for {stream_id}")

            except subprocess.TimeoutExpired:
                self.logger.warning(f"Force killing relay for {stream_id}")
                process.kill()
                del self.relays[stream_id]
            except Exception as e:
                self.logger.error(f"Error stopping RTSP relay for {stream_id}: {e}")

    def get_relay_info(self, stream_id):
        """Get relay information for a stream"""
        return self.relays.get(stream_id)

    def stop_all(self):
        """Stop all relays"""
        self.logger.info("Stopping all RTSP relays...")
        for stream_id in list(self.relays.keys()):
            self.stop_relay(stream_id)
        self.logger.info("All RTSP relays stopped")
