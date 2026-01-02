"""
Hybrid streamer: Pure GStreamer hardware pipeline + Python motion detection.
Maximum NVDEC/NVENC utilization while keeping intelligent motion features.
"""

import subprocess
import threading
import time
import queue
from pathlib import Path
import logging
import json
from datetime import datetime
import cv2
import shutil

from motion_detector import MotionDetector
from hardware_pipeline import HardwarePipeline


class Streamer:
    """Hybrid streamer with continuous hardware pipeline and motion-aware chunk management"""

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
        
        # Hardware pipeline (runs independently, always encoding)
        self.hw_pipeline = None

        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=config.get('motion_zones', []),
            cooldown=config.get('motion_cooldown', 10),
            detection_scale=config.get('motion_detection_scale', 0.25),
            blur_kernel=config.get('motion_blur_kernel', 5),
            frame_skip=config.get('motion_frame_skip', 2),
        )

        self.logger = self._setup_logger()
        self._instances.append(self)

        # Check for GStreamer
        self._gst_available = self._check_gstreamer()
        
        # Hardware pipeline will be started/stopped based on motion
        # NOT started automatically anymore
        
        # Start motion detection thread (uses lightweight OpenCV capture)
        threading.Thread(target=self._motion_detection_loop, daemon=True).start()
        
        # Start pipeline manager thread (starts/stops pipeline based on motion)
        threading.Thread(target=self._pipeline_manager_loop, daemon=True).start()

    def _check_gstreamer(self):
        """Check GStreamer availability"""
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
                self.logger.warning("⚠ GStreamer missing NVIDIA plugins")
                return False
        except Exception as e:
            self.logger.warning(f"⚠ GStreamer not available: {e}")
            return False

    def _setup_logger(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger(f'streamer-{self.stream_id}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            fh = logging.FileHandler(log_dir / f'{self.stream_id}.log')
            fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            logger.addHandler(fh)
        
        return logger

    def _get_target_fps(self):
        """Get target FPS based on motion state (required by API)"""
        if self.motion_active:
            return int(self.config.get('motion_high_fps', 25))
        return int(self.config.get('motion_low_fps', 1))

    def _motion_detection_loop(self):
        """Lightweight motion detection using downscaled OpenCV capture"""
        self.logger.info("Starting motion detection loop (lightweight CPU capture)")
        
        # Lightweight capture for motion detection only (downscaled, low FPS)
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.logger.error("Failed to open RTSP for motion detection")
            return
        
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Downscale for motion detection (saves CPU)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        
        last_motion_state = False
        frame_count = 0
        last_log = time.time()
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue
            
            frame_count += 1
            
            # Detect motion
            motion = self.detector.detect(frame)
            
            if motion != last_motion_state:
                self.motion_active = motion
                status = "MOTION ACTIVE" if motion else "MOTION INACTIVE"
                self.logger.info(f"{status}")
                self._log_motion_event("MOTION" if motion else "IDLE", self._get_target_fps())
                last_motion_state = motion
            
            # Log activity
            if time.time() - last_log > 10:
                self.logger.info(f"Motion detection: {frame_count} frames analyzed (CPU-lightweight)")
                last_log = time.time()
            
            time.sleep(0.2)  # 5 FPS for motion detection (very lightweight)
        
        cap.release()
        self.logger.info("Motion detection stopped")

    def _pipeline_manager_loop(self):
        """Start/stop hardware pipeline based on motion detection - matches old behavior"""
        self.logger.info("Starting pipeline manager (motion-triggered)")
        
        pipeline_running = False
        last_chunk_time = 0
        chunk_duration = int(self.config.get('chunk_duration', 5))
        
        hw_chunk_dir = Path('tmp/hw_chunks') / self.stream_id
        output_dir = Path('tmp/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        while self.running:
            try:
                current_time = time.time()
                
                # OLD BEHAVIOR: Wait for motion, just like the old version
                if not self.motion_active:
                    # Stop pipeline if motion ended
                    if pipeline_running:
                        self.logger.info("⏹ Motion ended. Stopping pipeline and saving final chunks...")
                        
                        # Wait a moment for final chunk to complete
                        time.sleep(2)
                        
                        # Save all remaining chunks
                        if hw_chunk_dir.exists():
                            chunks = list(hw_chunk_dir.glob('*.mp4'))
                            if chunks:
                                self.logger.info(f"Saving {len(chunks)} final chunks...")
                                for chunk in chunks:
                                    dest = output_dir / chunk.name
                                    if not dest.exists() and chunk.stat().st_size > 1000:
                                        try:
                                            shutil.move(str(chunk), str(dest))
                                            self.logger.info(f"✓ Saved final chunk: {chunk.name}")
                                            self._queue_chunk_upload(dest)
                                        except Exception as e:
                                            self.logger.error(f"Failed to move final chunk: {e}")
                        
                        # Now stop the pipeline
                        if self.hw_pipeline:
                            self.hw_pipeline.stop()
                            self.hw_pipeline = None
                        pipeline_running = False
                    time.sleep(0.2)  # Same as old version
                    continue
                
                # Motion is active - ensure pipeline is running
                if not pipeline_running:
                    if self._gst_available and self.config.get('use_hardware_pipeline', True):
                        self.logger.info("🎬 Motion detected! Starting hardware pipeline...")
                        self.hw_pipeline = HardwarePipeline(self.stream_id, self.rtsp_url, self.config)
                        self.hw_pipeline.start()
                        pipeline_running = True
                        last_chunk_time = 0  # Reset to enable immediate logging
                        self.logger.info(f"Chunks will be created in: {hw_chunk_dir}")
                
                # Process chunks while motion is active (OLD BEHAVIOR: continuous during motion)
                if pipeline_running:
                    if hw_chunk_dir.exists():
                        chunks = sorted(hw_chunk_dir.glob('*.mp4'), key=lambda p: p.stat().st_mtime)
                        
                        # Always log when chunks are found
                        if chunks:
                            self.logger.info(f"📹 Found {len(chunks)} chunks in {hw_chunk_dir}")
                        
                        for chunk in chunks:
                            chunk_age = current_time - chunk.stat().st_mtime
                            chunk_size = chunk.stat().st_size
                            
                            self.logger.info(f"Processing {chunk.name}: age={chunk_age:.1f}s, size={chunk_size} bytes")
                            
                            # Move chunks that are complete:
                            # 1. At least 1 second old (ensure file is closed by GStreamer)
                            # 2. Has some data (not empty)
                            if chunk_age > 1 and chunk_size > 1000:
                                dest = output_dir / chunk.name
                                if not dest.exists():
                                    try:
                                        shutil.move(str(chunk), str(dest))
                                        self.logger.info(f"✓ Saved motion chunk: {chunk.name} ({chunk_size} bytes) to {dest}")
                                        
                                        # Queue for upload (same as old version)
                                        self._queue_chunk_upload(dest)
                                    except Exception as e:
                                        self.logger.error(f"Failed to move chunk {chunk.name}: {e}")
                                else:
                                    self.logger.warning(f"Destination already exists: {dest}")
                            else:
                                self.logger.debug(f"Waiting for chunk to complete: age={chunk_age:.1f}s, size={chunk_size}")
                    else:
                        # Log if chunk directory doesn't exist yet
                        self.logger.warning(f"⚠ Pipeline running but directory missing: {hw_chunk_dir}")
                
                time.sleep(0.5)  # Check frequently like old version
                
            except Exception as e:
                self.logger.error(f"Pipeline manager error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)

    def _queue_chunk_upload(self, chunk_path):
        """Queue chunk for cloud upload"""
        try:
            from cloud_uploader import cloud_uploader
            
            if cloud_uploader and cloud_uploader.enabled:
                # Extract timestamp from filename if possible
                ts_start = int(chunk_path.stat().st_mtime)
                ts_end = ts_start + int(self.config.get('chunk_duration', 5))
                
                stream_name = self.config.get('name', self.stream_id)
                cloud_uploader.queue_chunk(chunk_path, stream_name, ts_start, ts_end)
                self.logger.info(f"Queued for upload: {chunk_path.name}")
        except Exception as e:
            self.logger.error(f"Upload queue error: {e}")

    def _log_motion_event(self, status, fps):
        """Log motion event"""
        try:
            log_dir = Path('logs')
            event_file = log_dir / f'events_{self.stream_id}.json'
            
            event = {
                'timestamp': datetime.now().isoformat(),
                'status': status,
                'fps': fps
            }
            
            events = []
            if event_file.exists():
                try:
                    with open(event_file, 'r') as f:
                        events = json.load(f)
                except:
                    events = []
            
            events.append(event)
            events = events[-100:]
            
            with open(event_file, 'w') as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")

    def update_config(self, config):
        """Update configuration"""
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
            self.logger.warning(f"Config update failed: {e}")

    def stop(self):
        """Stop the streamer"""
        self.logger.info("Stopping streamer...")
        self.running = False
        
        # Stop hardware pipeline
        if self.hw_pipeline:
            self.hw_pipeline.stop()
        
        time.sleep(1)
        
        try:
            if self in self._instances:
                self._instances.remove(self)
        except:
            pass
        
        self.logger.info("✓ Streamer stopped")

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Set low quality mode"""
        with cls._lock:
            cls._low_quality = enabled

    @classmethod
    def restart_all(cls):
        """Restart all streamers"""
        for inst in list(cls._instances):
            try:
                inst.logger.info("Config changed")
            except:
                pass