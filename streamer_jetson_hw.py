"""
Hardware-accelerated streamer for NVIDIA Jetson with nvv4l2decoder and nvv4l2h264enc

This implementation uses GStreamer pipelines with NVIDIA hardware acceleration
for both RTSP decoding and H.264 encoding on Jetson platforms.
"""

import subprocess
import shlex
import shutil
import threading
import time
import queue
from pathlib import Path
import logging
import json
from datetime import datetime

from motion_detector import MotionDetector


class Streamer:
    """Hardware-accelerated RTSP streamer with NVIDIA Jetson support.

    Uses nvv4l2decoder for hardware RTSP decoding and nvv4l2h264enc for 
    hardware H.264 encoding, matching the performance shown in your test output.
    """

    _instances = []
    _low_quality = False
    _lock = threading.Lock()
    _gst_path = shutil.which('gst-launch-1.0')

    def __init__(self, rtsp_url, config, stream_id):
        self.rtsp_url = rtsp_url
        self.stream_id = stream_id
        self.config = config
        self.motion_active = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True

        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=config.get('motion_zones', []),
            cooldown=config.get('motion_cooldown', 10),
            detection_scale=config.get('motion_detection_scale', 0.25),
            blur_kernel=config.get('motion_blur_kernel', 5),
            frame_skip=config.get('motion_frame_skip', 2),
        )

        self.default_bitrate = int(config.get('default_bitrate', 2000000))
        self.low_bitrate = int(config.get('low_bitrate', max(400000, self.default_bitrate // 4)))

        self.logger = self._setup_logger()

        self._instances.append(self)

        # Start threads
        threading.Thread(target=self._capture_loop_hw_gstreamer, daemon=True).start()
        threading.Thread(target=self._motion_loop, daemon=True).start()
        threading.Thread(target=self._chunking_loop, daemon=True).start()

    def _setup_logger(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger(f'streamer-{self.stream_id}')
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_dir / f'{self.stream_id}.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(fh)
        return logger

    def _log_motion_event(self, status, fps):
        """Log motion event to JSON file for event tracking"""
        try:
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            event_file = log_dir / f'events_{self.stream_id}.json'
            
            event = {
                'timestamp': datetime.now().isoformat(),
                'status': status,
                'fps': fps
            }
            
            # Load existing events
            events = []
            if event_file.exists():
                try:
                    with open(event_file, 'r') as f:
                        events = json.load(f)
                except:
                    events = []
            
            # Append new event and keep last 100 events
            events.append(event)
            events = events[-100:]
            
            # Save back to file
            with open(event_file, 'w') as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to log motion event: {e}")

    def _get_target_bitrate(self):
        if self._low_quality:
            return self.low_bitrate
        if not self.motion_active:
            return self.low_bitrate
        return self.default_bitrate

    def _get_target_fps(self):
        """Return target FPS based on motion state and config."""
        if self.motion_active:
            return int(self.config.get('motion_high_fps', 25))
        return int(self.config.get('motion_low_fps', 1))

    def _capture_loop_hw_gstreamer(self):
        """
        Hardware-accelerated RTSP capture using GStreamer with NVIDIA decoder.
        
        This uses the same pipeline structure as your test:
        rtspsrc -> rtph264depay -> h264parse -> nvv4l2decoder -> videoconvert
        """
        import cv2
        import numpy as np

        try:
            # GStreamer pipeline with NVIDIA hardware decoder
            # Matches the working test: rtspsrc ! rtph264depay ! h264parse ! nvv4l2decoder
            pipeline = (
                f"rtspsrc location={self.rtsp_url} latency=200 ! "
                f"rtph264depay ! "
                f"h264parse ! "
                f"nvv4l2decoder ! " # NVIDIA hardware decoder
                f"nvvidconv ! " # NVIDIA video converter
                f"video/x-raw,format=BGRx ! "
                f"videoconvert ! "
                f"video/x-raw,format=BGR ! "
                f"appsink name=sink emit-signals=true sync=false max-buffers=2 drop=true"
            )

            self.logger.info(f"Starting GStreamer HW pipeline: {pipeline[:100]}...")
            
            # Use OpenCV with GStreamer backend
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            
            if not cap.isOpened():
                self.logger.error("Failed to open GStreamer pipeline with hardware decoder")
                return False

            self.logger.info("✓ GStreamer NVIDIA hardware decoder pipeline started successfully")
            
            frame_count = 0
            last_frame_time = time.time()
            target_interval = 0.1  # 10 FPS for motion detection

            while self.running:
                ret, frame = cap.read()
                
                if not ret:
                    self.logger.warning("Failed to read frame from GStreamer pipeline, retrying...")
                    time.sleep(0.5)
                    continue

                frame_count += 1
                if frame_count % 100 == 0:
                    self.logger.info(f"✓ Captured {frame_count} frames (HW decode)")

                try:
                    if not self.frame_queue.full():
                        self.frame_queue.put(frame, block=False)
                except Exception:
                    pass

                # Dynamic sleep to maintain target FPS
                elapsed = time.time() - last_frame_time
                sleep_time = max(0, target_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_frame_time = time.time()

            cap.release()
            self.logger.info("GStreamer hardware decode capture loop ended")
            return True

        except Exception as e:
            self.logger.error(f"GStreamer hardware decode error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _chunking_loop(self):
        """Motion-triggered video chunking with NVIDIA hardware encoding."""
        import cv2
        import uuid
        
        while self.running:
            try:
                # Check config for chunking enabled
                chunking_enabled = self.config.get('chunking_enabled', False)
                chunk_duration = int(self.config.get('chunk_duration', 5))
                chunk_fps = int(self.config.get('chunk_fps', 2))
                
                if not chunking_enabled:
                    time.sleep(1)
                    continue
                
                # Wait for motion
                if not self.motion_active:
                    time.sleep(0.2)
                    continue
                
                # Start chunk capture
                frames = []
                start_time = time.time()
                
                while time.time() - start_time < chunk_duration and self.motion_active and self.running:
                    try:
                        frame = self.frame_queue.get(timeout=1)
                        frames.append(frame.copy())
                    except queue.Empty:
                        pass
                    time.sleep(1.0 / max(1, chunk_fps))
                
                if frames:
                    # Save chunk using NVIDIA hardware encoding
                    chunk_id = str(uuid.uuid4())[:8]
                    ts_start = int(start_time)
                    ts_end = int(time.time())
                    out_dir = Path('tmp/chunks')
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"{self.stream_id}_{chunk_id}.mp4"

                    # Use NVIDIA hardware encoder
                    success = self._encode_chunk_hw_nvidia(frames, out_path, chunk_fps)
                    
                    if not success:
                        self.logger.warning("NVIDIA hardware encoding failed, falling back to software")
                        success = self._encode_chunk_software(frames, out_path, chunk_fps)

                    if success:
                        self.logger.info(f"✓ Chunk saved: {out_path}")
                        self._upload_chunk_to_cloud(out_path, chunk_id, ts_start, ts_end)
                    else:
                        self.logger.error(f"✗ Failed to encode chunk {chunk_id}")
                        
            except Exception as e:
                self.logger.error(f"Chunking error: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(0.5)

    def _encode_chunk_hw_nvidia(self, frames, out_path, fps):
        """
        Encode video chunk using NVIDIA hardware encoder (nvv4l2h264enc).
        
        This matches the encoder used in your test output:
        nvv4l2h264enc ! h264parse ! qtmux
        """
        try:
            import cv2
            
            if not frames:
                return False

            h, w = frames[0].shape[:2]

            # GStreamer pipeline with NVIDIA hardware encoder
            # Matches test: appsrc ! nvvidconv ! nvv4l2h264enc ! h264parse ! qtmux
            pipeline = (
                f"appsrc ! "
                f"videoconvert ! "
                f"video/x-raw,format=I420,width={w},height={h},framerate={fps}/1 ! "
                f"nvvidconv ! " # NVIDIA video converter
                f"nvv4l2h264enc bitrate=1000000 ! " # NVIDIA hardware encoder, 1 Mbps
                f"h264parse ! "
                f"qtmux ! "
                f"filesink location={out_path}"
            )

            self.logger.info(f"Starting NVIDIA hardware encoding: {w}x{h} @ {fps}fps")
            self.logger.info(f"Pipeline: {pipeline[:100]}...")
            
            # Use gst-launch subprocess
            cmd = ['gst-launch-1.0', '-e'] + shlex.split(pipeline.replace('gst-launch-1.0', ''))
            
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Write frames to pipeline
            for frame in frames:
                try:
                    # Convert BGR to I420 (YUV)
                    yuv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
                    proc.stdin.write(yuv_frame.tobytes())
                except BrokenPipeError:
                    self.logger.warning("NVIDIA encoding pipe broken during write")
                    break

            proc.stdin.close()
            stdout, stderr = proc.communicate(timeout=15)

            success = proc.returncode == 0 and out_path.exists()

            if success:
                self.logger.info(f"✓ NVIDIA hardware encoding succeeded: {out_path.name}")
            else:
                self.logger.warning(f"✗ NVIDIA hardware encoding failed (returncode={proc.returncode})")
                if stderr:
                    error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                    self.logger.debug(f"GStreamer stderr: {error_msg}")

            return success

        except subprocess.TimeoutExpired:
            self.logger.error("NVIDIA hardware encoding timeout (>15s)")
            try:
                proc.kill()
            except:
                pass
            return False
        except Exception as e:
            self.logger.error(f"NVIDIA hardware encoding error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _encode_chunk_software(self, frames, out_path, fps):
        """Fallback software encoding using ffmpeg libx264."""
        try:
            import cv2
            
            if not frames:
                return False

            h, w = frames[0].shape[:2]

            preset = self.config.get('encoding_preset', 'ultrafast')
            crf = self.config.get('encoding_crf', 28)

            cmd = [
                'ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{w}x{h}',
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', preset,
                '-tune', 'zerolatency',
                '-crf', str(crf),
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                str(out_path)
            ]

            self.logger.info(f"Software encoding (libx264): {w}x{h} @ {fps}fps, preset={preset}, crf={crf}")
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            for frame in frames:
                try:
                    proc.stdin.write(frame.tobytes())
                except BrokenPipeError:
                    self.logger.warning("Software encoding pipe broken during write")
                    break

            proc.stdin.close()
            _, stderr = proc.communicate(timeout=15)

            success = proc.returncode == 0 and out_path.exists()

            if success:
                self.logger.info(f"✓ Software encoding succeeded: {out_path.name}")
            else:
                self.logger.warning(f"✗ Software encoding failed (returncode={proc.returncode})")

            return success

        except Exception as e:
            self.logger.error(f"Software encoding error: {e}")
            return False

    def _upload_chunk_to_cloud(self, chunk_path, chunk_id, ts_start, ts_end):
        """Upload chunk to cloud server with authentication."""
        try:
            from cloud_uploader import cloud_uploader
            
            if cloud_uploader and cloud_uploader.enabled:
                stream_name = self.config.get('name', self.stream_id)
                cloud_uploader.queue_chunk(chunk_path, stream_name, ts_start, ts_end)
                self.logger.info(f"Queued chunk for cloud upload: {chunk_path.name}")
            else:
                self.logger.debug(f"Cloud upload disabled or not configured")
        except Exception as e:
            self.logger.error(f"Error queuing chunk for upload: {e}")

    def _motion_loop(self):
        last_bitrate = None
        last_fps = None
        last_motion_state = False
        motion_frame_count = 0
        no_motion_frame_count = 0
        
        self.logger.info("Starting motion detection loop")
        
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except queue.Empty:
                self.motion_active = False
                time.sleep(0.5)
                continue
            
            # Get motion detection result
            motion = self.detector.detect(frame)
            
            # Track motion stats
            if motion:
                motion_frame_count += 1
                no_motion_frame_count = 0
            else:
                no_motion_frame_count += 1
                motion_frame_count = 0
            
            # Log when motion starts/stops
            if motion_frame_count == 1:
                self.logger.info("✓ Motion STARTED being detected")
            elif no_motion_frame_count == 1:
                self.logger.info("✓ Motion STOPPED being detected (cooldown may still be active)")
            
            # Update motion state and log events
            if motion != last_motion_state:
                self.motion_active = motion
                target_fps = self._get_target_fps()
                
                status = "MOTION" if motion else "IDLE"
                self.logger.info(f"{status}: FPS {target_fps}")
                self._log_motion_event(status, target_fps)
                
                last_motion_state = motion
            
            time.sleep(0.05)
        
        self.logger.info("Motion detection loop ended")

    def update_config(self, config):
        """Update streamer configuration and motion detector settings."""
        self.config = config
        try:
            self.detector.update_settings(
                sensitivity=config.get('motion_sensitivity'),
                min_area=config.get('motion_min_area'),
                zones=config.get('motion_zones'),
                cooldown=config.get('motion_cooldown')
            )
        except Exception:
            pass

    def stop(self):
        """Stop the streamer gracefully."""
        self.running = False
        try:
            if self in self._instances:
                self._instances.remove(self)
        except Exception:
            pass

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Enable/disable low-quality mode for all streamers."""
        with cls._lock:
            cls._low_quality = enabled

    @classmethod
    def restart_all(cls):
        """Restart all active streamers."""
        for inst in list(cls._instances):
            try:
                # For hardware acceleration, we don't restart pipelines
                # Just update internal state
                inst.logger.info("Configuration updated")
            except Exception:
                pass