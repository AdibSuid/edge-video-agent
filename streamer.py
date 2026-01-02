"""
GStreamer-based streamer with NVIDIA hardware acceleration for Jetson.
Uses filesrc method for maximum reliability with NVENC.
"""

import subprocess
import shutil
import threading
import time
import queue
from pathlib import Path
import logging
import json
from datetime import datetime
import cv2
import numpy as np

from motion_detector import MotionDetector


class Streamer:
    """GStreamer-based RTSP streamer with NVIDIA hardware acceleration.

    Features:
    - NVDEC hardware decoding for RTSP streams
    - NVENC hardware encoding for video chunks (filesrc method)
    - Motion-triggered adaptive FPS
    - Automatic fallback to software when hardware unavailable
    """

    _instances = []
    _low_quality = False
    _lock = threading.Lock()

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

        # Check for GStreamer availability
        self._gst_available = self._check_gstreamer()
        
        # Start threads
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._motion_loop, daemon=True).start()
        threading.Thread(target=self._chunking_loop, daemon=True).start()

    def _check_gstreamer(self):
        """Check if GStreamer is available and has NVIDIA plugins"""
        try:
            result = subprocess.run(
                ['gst-inspect-1.0', 'nvv4l2decoder'],
                capture_output=True,
                timeout=5
            )
            has_nvdec = result.returncode == 0
            
            result = subprocess.run(
                ['gst-inspect-1.0', 'nvv4l2h264enc'],
                capture_output=True,
                timeout=5
            )
            has_nvenc = result.returncode == 0
            
            if has_nvdec and has_nvenc:
                self.logger.info("✓ GStreamer with NVIDIA plugins available")
                return True
            else:
                self.logger.warning("⚠ GStreamer found but missing NVIDIA plugins")
                return False
        except Exception as e:
            self.logger.warning(f"⚠ GStreamer not available: {e}")
            return False

    def _setup_logger(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger(f'streamer-{self.stream_id}')
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not logger.handlers:
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
        """Return target FPS based on motion state"""
        if self.motion_active:
            return int(self.config.get('motion_high_fps', 25))
        return int(self.config.get('motion_low_fps', 1))

    def _build_gstreamer_pipeline(self):
        """Build GStreamer pipeline for RTSP with NVIDIA hardware decode"""
        target_fps = self._get_target_fps()
        
        pipeline = (
            f"rtspsrc location={self.rtsp_url} latency=200 protocols=tcp ! "
            "queue max-size-buffers=2 leaky=downstream ! "
            "rtph264depay ! "
            "h264parse ! "
            "nvv4l2decoder enable-max-performance=1 ! "  # NVIDIA hardware decoder
            "nvvidconv ! "  # NVIDIA format converter
            "video/x-raw,format=BGRx ! "
            "videoconvert ! "
            "video/x-raw,format=BGR ! "
            f"videorate ! video/x-raw,framerate={target_fps}/1 ! "
            "appsink drop=1 max-buffers=2 sync=false"
        )
        
        return pipeline

    def _capture_loop(self):
        """Capture loop with GStreamer hardware decode"""
        use_hw_decode = self.config.get('use_hardware_decode', True) and self._gst_available
        
        if use_hw_decode:
            self.logger.info(f"Starting GStreamer NVDEC capture for {self.rtsp_url}")
            success = self._capture_loop_gstreamer()
            if success:
                return
            self.logger.warning("GStreamer capture failed, falling back to OpenCV")
        
        # Fallback to OpenCV software decoding
        self._capture_loop_opencv()

    def _capture_loop_gstreamer(self):
        """GStreamer-based capture with NVIDIA hardware decode"""
        try:
            pipeline = self._build_gstreamer_pipeline()
            self.logger.info(f"GStreamer pipeline: {pipeline[:100]}...")
            
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            
            if not cap.isOpened():
                self.logger.error("Failed to open GStreamer pipeline")
                return False

            self.logger.info("✓ GStreamer NVDEC capture started successfully")
            frame_count = 0
            last_log_time = time.time()
            
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame from GStreamer")
                    time.sleep(0.5)
                    continue

                frame_count += 1
                
                # Log every 5 seconds instead of every 100 frames
                if time.time() - last_log_time > 5:
                    self.logger.info(f"NVDEC: {frame_count} frames captured")
                    last_log_time = time.time()

                try:
                    if not self.frame_queue.full():
                        self.frame_queue.put(frame, block=False)
                except:
                    pass

                time.sleep(0.01)  # Small sleep to prevent CPU spin

            cap.release()
            self.logger.info("GStreamer NVDEC capture ended")
            return True

        except Exception as e:
            self.logger.error(f"GStreamer capture error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _capture_loop_opencv(self):
        """Fallback OpenCV software decode"""
        self.logger.info(f"Starting OpenCV software decode for {self.rtsp_url}")
        
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
            return

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.logger.info("✓ OpenCV capture started successfully")
        
        frame_count = 0
        last_log_time = time.time()
        target_interval = 0.1

        while self.running:
            ret, frame = cap.read()
            if not ret:
                self.logger.warning("Failed to read frame, retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1
            if time.time() - last_log_time > 5:
                self.logger.info(f"OpenCV: {frame_count} frames captured")
                last_log_time = time.time()

            try:
                if not self.frame_queue.full():
                    self.frame_queue.put(frame, block=False)
            except:
                pass

            elapsed = time.time() - frame_count * target_interval
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()
        self.logger.info("OpenCV capture ended")

    def _motion_loop(self):
        """Motion detection loop"""
        last_motion_state = False
        self.logger.info("Starting motion detection loop")
        
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except queue.Empty:
                self.motion_active = False
                time.sleep(0.5)
                continue
            
            motion = self.detector.detect(frame)
            
            if motion != last_motion_state:
                self.motion_active = motion
                target_fps = self._get_target_fps()
                
                status = "MOTION ACTIVE" if motion else "Motion INACTIVE"
                self.logger.info(f"{status}: FPS -> {target_fps}")
                self._log_motion_event("MOTION" if motion else "IDLE", target_fps)
                
                last_motion_state = motion
            
            time.sleep(0.05)
        
        self.logger.info("Motion detection loop ended")

    def _chunking_loop(self):
        """Motion-triggered video chunking with NVIDIA hardware encoding"""
        import uuid
        
        while self.running:
            try:
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
                
                # Capture frames during motion
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
                    chunk_id = str(uuid.uuid4())[:8]
                    ts_start = int(start_time)
                    ts_end = int(time.time())
                    out_dir = Path('tmp/chunks')
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"{self.stream_id}_{chunk_id}.mp4"

                    # Try hardware encoding first
                    success = False
                    if self._gst_available:
                        success = self._encode_chunk_gstreamer(frames, out_path, chunk_fps)
                    
                    if not success:
                        self.logger.warning("Hardware encoding unavailable, using software")
                        success = self._encode_chunk_software(frames, out_path, chunk_fps)

                    if success:
                        self.logger.info(f"✓ Chunk saved: {out_path.name}")
                        self._upload_chunk_to_cloud(out_path, chunk_id, ts_start, ts_end)
                    else:
                        self.logger.error(f"✗ Failed to encode chunk {chunk_id}")
                        
            except Exception as e:
                self.logger.error(f"Chunking error: {e}")
                import traceback
                traceback.print_exc()
            
            time.sleep(0.5)

    def _encode_chunk_gstreamer(self, frames, out_path, fps):
        """Encode video chunk using GStreamer NVENC with filesrc method (fixed pipeline)"""
        temp_raw = None
        try:
            if not frames:
                return False

            h, w = frames[0].shape[:2]
            bitrate = int(self.config.get('chunk_bitrate', 2000000))

            # Create temporary raw YUV file
            temp_raw = Path('tmp/chunks') / f"temp_{self.stream_id}_{int(time.time() * 1000)}.yuv"
            temp_raw.parent.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"NVENC encoding: {w}x{h} @ {fps}fps, bitrate={bitrate}, frames={len(frames)}")

            # Write all frames to temporary YUV file
            try:
                with open(temp_raw, 'wb') as f:
                    for i, frame in enumerate(frames):
                        try:
                            # Convert BGR to YUV I420
                            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
                            f.write(yuv.tobytes())
                        except Exception as e:
                            self.logger.error(f"Frame conversion error at {i}: {e}")
                            if temp_raw.exists():
                                temp_raw.unlink()
                            return False
                
                if not temp_raw.exists() or temp_raw.stat().st_size == 0:
                    self.logger.error("Failed to write temp YUV file (empty or missing)")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Failed to write temp YUV file: {e}")
                if temp_raw and temp_raw.exists():
                    temp_raw.unlink()
                return False

            # FIXED: Proper GStreamer pipeline with explicit caps
            pipeline = (
                f"filesrc location={temp_raw} ! "
                f"videoparse width={w} height={h} format=i420 framerate={fps}/1 ! "  # Use videoparse instead of rawvideoparse
                f"video/x-raw,format=I420,width={w},height={h},framerate={fps}/1 ! "
                f"nvvidconv ! "  # NVIDIA video converter
                f"video/x-raw(memory:NVMM),format=I420 ! "  # NVMM memory for zero-copy
                f"nvv4l2h264enc bitrate={bitrate} preset-level=1 insert-sps-pps=true ! "
                f"h264parse ! "
                f"qtmux ! "
                f"filesink location={out_path}"
            )

            # Build command as list (don't use split() - it breaks quoted args)
            cmd = ['gst-launch-1.0', '-e', pipeline]
            
            self.logger.info(f"Running GStreamer NVENC...")
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30,
                    check=False
                )
                
                success = result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0

                if success:
                    file_size = out_path.stat().st_size
                    self.logger.info(f"✓ NVENC succeeded: {out_path.name} ({file_size} bytes, {len(frames)} frames)")
                else:
                    stderr_text = result.stderr.decode('utf-8', errors='ignore')
                    self.logger.warning(f"✗ NVENC failed (rc={result.returncode})")
                    # Log full stderr for debugging
                    if stderr_text:
                        self.logger.warning(f"GStreamer stderr: {stderr_text[:1000]}")

            except subprocess.TimeoutExpired:
                self.logger.error("NVENC timeout (>30s)")
                success = False

            # Cleanup temp file
            try:
                if temp_raw and temp_raw.exists():
                    temp_raw.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to delete temp file: {e}")

            return success

        except Exception as e:
            self.logger.error(f"NVENC error: {e}")
            import traceback
            traceback.print_exc()
            
            # Cleanup on error
            try:
                if temp_raw and temp_raw.exists():
                    temp_raw.unlink()
            except:
                pass
                
            return False

    def _encode_chunk_software(self, frames, out_path, fps):
        """Fallback software encoding using OpenCV VideoWriter"""
        try:
            if not frames:
                return False

            h, w = frames[0].shape[:2]
            
            self.logger.info(f"Software encoding: {w}x{h} @ {fps}fps, {len(frames)} frames")
            
            # Use mp4v codec (widely supported)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

            if not writer.isOpened():
                self.logger.error("Failed to open VideoWriter")
                return False

            for i, frame in enumerate(frames):
                writer.write(frame)

            writer.release()

            success = out_path.exists() and out_path.stat().st_size > 0

            if success:
                file_size = out_path.stat().st_size
                self.logger.info(f"✓ Software encode succeeded: {out_path.name} ({file_size} bytes)")
            else:
                self.logger.error("✗ Software encode produced empty file")

            return success

        except Exception as e:
            self.logger.error(f"Software encode error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _upload_chunk_to_cloud(self, chunk_path, chunk_id, ts_start, ts_end):
        """Upload chunk to cloud server"""
        try:
            from cloud_uploader import cloud_uploader
            
            if cloud_uploader and cloud_uploader.enabled:
                stream_name = self.config.get('name', self.stream_id)
                cloud_uploader.queue_chunk(chunk_path, stream_name, ts_start, ts_end)
                self.logger.info(f"Queued for cloud upload: {chunk_path.name}")
            else:
                self.logger.debug("Cloud upload disabled")
        except Exception as e:
            self.logger.error(f"Upload queue error: {e}")

    def update_config(self, config):
        """Update configuration and motion detector settings"""
        self.config = config
        try:
            self.detector.update_settings(
                sensitivity=config.get('motion_sensitivity'),
                min_area=config.get('motion_min_area'),
                zones=config.get('motion_zones'),
                cooldown=config.get('motion_cooldown'),
                detection_scale=config.get('motion_detection_scale'),
                blur_kernel=config.get('motion_blur_kernel'),
                frame_skip=config.get('motion_frame_skip')
            )
            self.logger.info("Configuration updated")
        except Exception as e:
            self.logger.warning(f"Failed to update detector settings: {e}")

    def stop(self):
        """Stop the streamer gracefully"""
        self.logger.info(f"Stopping streamer {self.stream_id}...")
        self.running = False
        time.sleep(1)  # Give threads time to exit
        
        try:
            if self in self._instances:
                self._instances.remove(self)
        except Exception:
            pass
        
        self.logger.info(f"Streamer {self.stream_id} stopped")

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Enable/disable low-quality mode for all streamers"""
        with cls._lock:
            cls._low_quality = enabled
            for inst in list(cls._instances):
                try:
                    inst.logger.info(f"Low quality mode: {enabled}")
                except Exception:
                    pass

    @classmethod
    def restart_all(cls):
        """Restart all active streamers (called when config changes)"""
        for inst in list(cls._instances):
            try:
                inst.logger.info("Config changed - settings will apply to new chunks")
            except Exception:
                pass