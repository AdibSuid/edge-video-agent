#!/usr/bin/env python3
"""
RTMP Push Manager
Pushes RTSP camera streams to cloud MediaMTX server via RTMP protocol
Includes auto-restart and connection monitoring (watchdog)
"""

import subprocess
import threading
import time
import logging
from pathlib import Path
import signal
import os
import shutil


class RTMPPushManager:
    """
    Manages RTMP push streams to cloud MediaMTX server with auto-restart

    Architecture:
    Camera RTSP → GStreamer → RTMP Push → Cloud MediaMTX (port 1935)
    Cloud MediaMTX converts → RTSP (port 8554) → DeepStream
    """

    def __init__(self, config):
        self.config = config
        self.cloud_rtmp_url = config.get('cloud_rtmp_url', '')
        self.streams = {}  # stream_id -> stream info
        self.logger = self._setup_logger()
        self.monitoring = True

        # Find gst-launch-1.0 executable
        self.gst_launch_path = shutil.which('gst-launch-1.0')
        if not self.gst_launch_path:
            # Try common Windows locations
            common_paths = [
                r'C:\Program Files\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe',
                r'C:\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe',
                r'C:\Program Files (x86)\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe'
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self.gst_launch_path = path
                    break
        
        if not self.gst_launch_path:
            self.logger.error("gst-launch-1.0 not found. Please install GStreamer from https://gstreamer.freedesktop.org/download/")
        else:
            self.logger.info(f"Found gst-launch-1.0 at: {self.gst_launch_path}")

        # Start monitoring thread
        threading.Thread(target=self._monitor_streams, daemon=True).start()

    def _setup_logger(self):
        logger = logging.getLogger('rtmp-push')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - RTMP Push - %(message)s'))
            logger.addHandler(handler)
        return logger

    def start_push(self, stream_id, source_rtsp_url):
        """
        Start RTMP push for a stream using GStreamer

        Uses hardware decoding/encoding on Jetson if available,
        falls back to software on other platforms
        """
        if stream_id in self.streams:
            self.logger.info(f"RTMP push already running for {stream_id}")
            return True

        if not self.gst_launch_path:
            self.logger.error("gst-launch-1.0 not found. Cannot start RTMP push.")
            return False

        if not self.cloud_rtmp_url:
            self.logger.error("No cloud_rtmp_url configured in config.yaml")
            return False

        try:
            # Build RTMP destination URL
            rtmp_destination = f"{self.cloud_rtmp_url}/live/{stream_id}"

            # GStreamer pipeline for RTMP push
            # Strategy: Minimize CPU by avoiding re-encoding when possible
            # Just repackage H.264 stream into FLV/RTMP container

            pipeline = [
                self.gst_launch_path,
                'rtspsrc',
                f'location={source_rtsp_url}',
                'protocols=tcp',  # Force TCP for reliability
                'latency=200',
                '!', 'rtph264depay',
                '!', 'h264parse',
                '!', 'flvmux',
                'streamable=true',  # Important for RTMP streaming
                '!', 'rtmpsink',
                f'location={rtmp_destination}'
            ]

            self.logger.info(f"Starting RTMP push: {stream_id}")
            self.logger.info(f"  Source: {source_rtsp_url[:40]}...")
            self.logger.info(f"  Destination: {rtmp_destination}")

            # Start GStreamer process
            process = subprocess.Popen(
                pipeline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )

            self.streams[stream_id] = {
                'process': process,
                'source_url': source_rtsp_url,
                'rtmp_url': rtmp_destination,
                'pipeline': ' '.join(pipeline),
                'restart_count': 0,
                'last_restart': time.time(),
                'start_time': time.time()
            }

            self.logger.info(f"✓ RTMP push started for {stream_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start RTMP push for {stream_id}: {e}")
            return False

    def stop_push(self, stream_id):
        """Stop RTMP push for a stream"""
        if stream_id in self.streams:
            try:
                stream_info = self.streams[stream_id]
                process = stream_info['process']

                self.logger.info(f"Stopping RTMP push for {stream_id}")

                # Try graceful termination first
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()

                # Wait for termination
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination failed
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()

                del self.streams[stream_id]
                self.logger.info(f"✓ RTMP push stopped for {stream_id}")
                return True

            except Exception as e:
                self.logger.error(f"Error stopping RTMP push for {stream_id}: {e}")
                # Remove from dict even if stop failed
                if stream_id in self.streams:
                    del self.streams[stream_id]
                return False
        else:
            self.logger.warning(f"No RTMP push found for {stream_id}")
            return False

    def _monitor_streams(self):
        """
        Monitoring thread (watchdog)
        Checks if streams are still running and restarts them if they die
        """
        self.logger.info("RTMP push monitoring started")

        while self.monitoring:
            try:
                time.sleep(5)  # Check every 5 seconds

                for stream_id in list(self.streams.keys()):
                    stream_info = self.streams.get(stream_id)
                    if not stream_info:
                        continue

                    process = stream_info['process']

                    # Check if process is still running
                    if process.poll() is not None:
                        # Process has died
                        exit_code = process.returncode
                        
                        # Read stderr for debugging
                        try:
                            stdout, stderr = process.communicate(timeout=1)
                            if stderr:
                                self.logger.error(f"RTMP push stderr for {stream_id}: {stderr.decode('utf-8', errors='ignore')[:500]}")
                        except:
                            pass
                        
                        self.logger.warning(f"RTMP push died for {stream_id} (exit code: {exit_code})")

                        # Get source URL for restart
                        source_url = stream_info['source_url']
                        restart_count = stream_info['restart_count']

                        # Remove dead process
                        del self.streams[stream_id]

                        # Implement exponential backoff for restarts
                        # Wait longer between restarts to avoid hammering the server
                        backoff_time = min(2 ** restart_count, 60)  # Max 60 seconds

                        self.logger.info(f"Restarting RTMP push for {stream_id} in {backoff_time}s (attempt {restart_count + 1})")
                        time.sleep(backoff_time)

                        # Restart the push
                        if self.start_push(stream_id, source_url):
                            # Increment restart counter
                            if stream_id in self.streams:
                                self.streams[stream_id]['restart_count'] = restart_count + 1
                                self.logger.info(f"✓ RTMP push restarted for {stream_id}")
                        else:
                            self.logger.error(f"✗ Failed to restart RTMP push for {stream_id}")

            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
                continue

    def get_stream_status(self, stream_id):
        """Get status information for a stream"""
        if stream_id not in self.streams:
            return None

        stream_info = self.streams[stream_id]
        process = stream_info['process']

        uptime = time.time() - stream_info['start_time']

        return {
            'stream_id': stream_id,
            'running': process.poll() is None,
            'rtmp_url': stream_info['rtmp_url'],
            'restart_count': stream_info['restart_count'],
            'uptime_seconds': int(uptime),
            'pid': process.pid
        }

    def get_all_streams_status(self):
        """Get status for all streams"""
        return {
            stream_id: self.get_stream_status(stream_id)
            for stream_id in self.streams.keys()
        }

    def stop_all(self):
        """Stop all RTMP push streams"""
        self.logger.info("Stopping all RTMP push streams")
        self.monitoring = False

        for stream_id in list(self.streams.keys()):
            self.stop_push(stream_id)

        self.logger.info("All RTMP push streams stopped")
