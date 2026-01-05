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
        
        # Tapway-style recording parameters
        self.pre_record_buffer = config.get('pre_record_buffer', 0)
        self.motion_end_time = 0  # Track when motion ended
        self.recording_start_time = 0  # Track recording duration
        
        # Hardware pipeline (runs independently, always encoding)
        self.hw_pipeline = None

        # Get zones based on zone_mode (global config)
        zone_mode = config.get('zone_mode', 'all')
        if zone_mode == 'individual':
            # Use per-camera zones
            zones = config.get('motion_zones', [])
        else:
            # Use global zones from root config
            from app import config as global_config
            zones = global_config.get('motion_zones', [])

        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=zones,
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
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            self.logger.error("Failed to open RTSP for motion detection")
            return
        
        # Minimize latency for better motion detection responsiveness
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
        cap.set(cv2.CAP_PROP_FPS, 10)  # Request 10 FPS for motion detection
        
        # Downscale for motion detection (saves CPU)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        
        last_motion_state = False
        frame_count = 0
        last_log = time.time()
        last_frame_time = time.time()
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)  # Shorter retry on failure
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
            
            # Log activity every 30 seconds
            if time.time() - last_log > 30:
                fps = frame_count / (time.time() - last_log + 0.001)
                self.logger.info(f"Motion detection: {frame_count} frames analyzed ({fps:.1f} FPS)")
                last_log = time.time()
                frame_count = 0
            
            # Throttle to ~10 FPS for motion detection (better than old 5 FPS)
            time.sleep(0.1)
        
        cap.release()
        self.logger.info("Motion detection stopped")

    def _pipeline_manager_loop(self):
        """Start/stop hardware pipeline based on motion - creates fixed-duration chunks"""
        self.logger.info("Starting pipeline manager (motion-triggered chunked recording)")
        
        pipeline_running = False
        output_dir = Path('tmp/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        recording_session_start = None  # Track when recording session started
        
        while self.running:
            try:
                # Check config for chunking enabled
                chunking_enabled = self.config.get('chunking_enabled', False)
                if not chunking_enabled:
                    time.sleep(1)
                    continue
                
                # Wait for motion
                if not self.motion_active:
                    if pipeline_running:
                        # Track when motion ended
                        if self.motion_end_time == 0:
                            self.motion_end_time = time.time()
                            chunk_duration = self.config.get('chunk_duration', 5)
                            
                            # Calculate how much time has elapsed since recording started
                            recording_elapsed = time.time() - self.recording_start_time
                            
                            # Calculate when the next chunk boundary will occur
                            # This ensures we stop at a chunk boundary, not in the middle
                            time_into_current_chunk = recording_elapsed % chunk_duration
                            time_until_next_boundary = chunk_duration - time_into_current_chunk
                            
                            self.logger.info(f"Motion ended. Will record for {time_until_next_boundary:.1f} more seconds to complete current chunk...")
                        
                        # Calculate time since motion ended
                        elapsed = time.time() - self.motion_end_time
                        chunk_duration = self.config.get('chunk_duration', 5)
                        
                        # Calculate time to wait until next chunk boundary
                        recording_elapsed = self.motion_end_time - self.recording_start_time
                        time_into_current_chunk = recording_elapsed % chunk_duration
                        time_until_next_boundary = chunk_duration - time_into_current_chunk
                        
                        # Wait for current chunk to complete at the chunk boundary
                        if elapsed >= time_until_next_boundary:
                            self.logger.info("⏹ Chunk boundary reached. Stopping pipeline...")
                            
                            # Stop the pipeline
                            if self.hw_pipeline:
                                self.hw_pipeline.stop()
                                self.hw_pipeline = None
                            pipeline_running = False
                            
                            # Give GStreamer time to finalize files
                            time.sleep(2)
                            
                            # Upload all chunks created during this session
                            if recording_session_start:
                                self._upload_session_chunks(recording_session_start)
                            
                            recording_session_start = None
                            self.motion_end_time = 0
                            self.recording_start_time = 0
                    
                    time.sleep(0.2)
                    continue
                
                # Motion is active
                # Reset motion end time if motion reactivates
                if self.motion_end_time > 0:
                    self.logger.info("🔄 Motion detected again! Continuing recording...")
                    self.motion_end_time = 0
                
                # Start pipeline for this event
                if not pipeline_running:
                    if self._gst_available and self.config.get('use_hardware_pipeline', True):
                        recording_session_start = time.time()
                        
                        self.logger.info(f"🎬 Motion detected! Starting chunked recording (chunk_duration={self.config.get('chunk_duration', 5)}s)")
                        
                        # Start hardware pipeline - it will create chunks automatically
                        self.hw_pipeline = HardwarePipeline(
                            self.stream_id, 
                            self.rtsp_url, 
                            self.config,
                            output_file=None  # splitmuxsink handles filenames
                        )
                        self.hw_pipeline.start()
                        pipeline_running = True
                        self.recording_start_time = time.time()
                        self.logger.info("✓ Hardware pipeline recording with fixed-duration chunks")
                
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Pipeline manager error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    
    def _upload_session_chunks(self, session_start_time):
        """Upload all chunks created during a recording session"""
        try:
            output_dir = Path('tmp/chunks')
            if not output_dir.exists():
                return
            
            # Find all chunks created during this session (within 1 second of session start)
            session_timestamp = int(session_start_time)
            pattern = f"{self.stream_id}_{session_timestamp}_*.mp4"
            
            chunks = list(output_dir.glob(pattern))
            if not chunks:
                self.logger.warning(f"No chunks found for pattern: {pattern}")
                return
            
            # Sort by filename to upload in order
            chunks.sort()
            
            self.logger.info(f"Found {len(chunks)} chunk(s) to upload")
            
            for chunk_path in chunks:
                file_size = chunk_path.stat().st_size
                if file_size > 100000:  # Valid file (>100KB)
                    self._queue_chunk_upload(chunk_path)
                    self.logger.info(f"✓ Queued chunk: {chunk_path.name} ({file_size} bytes)")
                else:
                    self.logger.warning(f"⚠ Skipping small file: {chunk_path.name} ({file_size} bytes)")
                    
        except Exception as e:
            self.logger.error(f"Error uploading session chunks: {e}")
            import traceback
            traceback.print_exc()

    
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
        
        # Update Tapway-style recording parameters
        self.pre_record_buffer = config.get('pre_record_buffer', 0)
        
        try:
            # Get zones based on zone_mode
            zone_mode = config.get('zone_mode', 'all')
            if zone_mode == 'individual':
                zones = config.get('motion_zones', [])
            else:
                from app import config as global_config
                zones = global_config.get('motion_zones', [])
            
            self.detector.update_settings(
                sensitivity=config.get('motion_sensitivity'),
                min_area=config.get('motion_min_area'),
                zones=zones,
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

    def cleanup_logger(self):
        """Close all logger handlers to release file locks"""
        if self.logger:
            handlers = self.logger.handlers[:]
            for handler in handlers:
                handler.close()
                self.logger.removeHandler(handler)

        # Also cleanup hardware pipeline logger
        if self.hw_pipeline and hasattr(self.hw_pipeline, 'cleanup_logger'):
            self.hw_pipeline.cleanup_logger()

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