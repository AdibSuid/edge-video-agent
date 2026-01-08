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
<<<<<<< HEAD
    # Network adaptation hysteresis
    _network_hysteresis_hold_time = 10.0  # seconds
    _network_low_threshold = 2000000  # 2 Mbps
    _network_recovery_threshold = 3000000  # 3 Mbps
    _network_quality_change_time = None
    _pending_low_quality = False
    # path to ffmpeg if available on PATH (updated by autodetect)
    _ffmpeg_path = shutil.which('ffmpeg')
    # Class logger for static methods
    _logger = logging.getLogger(__name__)
=======
>>>>>>> f2d60f60a9d8ce1d2713282b0f4b4be0f6ca9e7a

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
            hysteresis_active=config.get('motion_hysteresis_active', 2.0),
            hysteresis_inactive=config.get('motion_hysteresis_inactive', 5.0),
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

<<<<<<< HEAD
        # If ffmpeg not present at startup, start a watcher thread that will
        # poll for ffmpeg appearing on PATH and start the pipeline when found.
        if not Streamer._ffmpeg_path:
            threading.Thread(target=self._ffmpeg_watcher, daemon=True).start()

        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._motion_loop, daemon=True).start()
        # Start chunking thread if enabled
        threading.Thread(target=self._chunking_loop, daemon=True).start()
        # do not start external processes in constructor for test-safety
    # SRT streaming logic removed for MediaMTX relay. Only RTSP and chunking remain.
    
    def _chunking_loop(self):
        """Motion-triggered video chunking pipeline."""
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
                        # Create a copy to avoid holding references to large frame buffers
                        frames.append(frame.copy())
                    except queue.Empty:
                        pass
                    time.sleep(1.0 / max(1, chunk_fps))
                if frames:
                    # Validate frames have consistent dimensions
                    heights = [f.shape[0] for f in frames]
                    widths = [f.shape[1] for f in frames]
                    if len(set(heights)) > 1 or len(set(widths)) > 1:
                        self.logger.warning(f"Inconsistent frame sizes detected: {set(zip(widths, heights))}, using most common")
                        # Find most common size
                        from collections import Counter
                        size_counts = Counter(zip(widths, heights))
                        target_w, target_h = size_counts.most_common(1)[0][0]
                        # Filter frames to matching size
                        frames = [f for f in frames if f.shape[0] == target_h and f.shape[1] == target_w]
                        self.logger.info(f"Filtered to {len(frames)} frames of size {target_w}x{target_h}")
                    
                    # Enforce minimum chunk duration (discard micro chunks)
                    min_chunk_duration = self.config.get('min_chunk_duration', 2.0)
                    min_frames = int(chunk_fps * min_chunk_duration)
                    if len(frames) < min_frames:
                        self.logger.info(f"Chunk too short ({len(frames)} frames < {min_frames} min), discarding")
                        continue
                    
                    if len(frames) < 2:
                        self.logger.warning(f"Too few frames ({len(frames)}) for encoding, skipping chunk")
                        continue
                    
                    # Log frame info
                    self.logger.info(f"Encoding chunk with {len(frames)} frames of shape {frames[0].shape}")

                    # Save chunk to file using hardware encoding if available
                    chunk_id = str(uuid.uuid4())[:8]
                    ts_start = int(start_time)
                    ts_end = int(time.time())
                    out_dir = Path('tmp/chunks')
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"{self.stream_id}_{chunk_id}.mp4"

                    # Try hardware encoding first if enabled, fallback to software
                    use_hw_encode = self.config.get('use_hardware_encode', True)
                    if use_hw_encode:
                        success = self._encode_chunk_hardware(frames, out_path, chunk_fps)
                        if not success:
                            self.logger.warning("Hardware encoding failed, falling back to software encoding")
                            success = self._encode_chunk_software(frames, out_path, chunk_fps)
                    else:
                        # Skip hardware encoding for platforms that don't support it
                        success = self._encode_chunk_software(frames, out_path, chunk_fps)

                    if success:
                        self.logger.info(f"Chunk saved: {out_path}")
                        # Upload to cloud
                        self._upload_chunk_to_cloud(out_path, chunk_id, ts_start, ts_end)
                    else:
                        self.logger.error(f"Failed to encode chunk {chunk_id}")
            except Exception as e:
                self.logger.error(f"Chunking error: {e}")
            time.sleep(0.5)

    def _encode_chunk_hardware(self, frames, out_path, fps):
        """Encode video chunk using hardware acceleration or optimized software encoding for Jetson Orin Nano."""
=======
    def _check_gstreamer(self):
        """Check GStreamer availability"""
>>>>>>> f2d60f60a9d8ce1d2713282b0f4b4be0f6ca9e7a
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
<<<<<<< HEAD
                # Optimized software encoding for Orin Nano and other platforms
                # Use libx264 with GPU-accelerated processing where possible
                encoder = 'libx264'
                encoder_opts = [
                    '-preset', 'ultrafast',  # Fastest preset for low latency
                    '-tune', 'zerolatency',  # Optimize for low latency
                    '-crf', '23',            # Quality setting (lower = better quality)
                    '-maxrate', '2M',        # Max bitrate
                    '-bufsize', '4M',        # Buffer size
                    '-threads', '0',         # Auto-detect threads
                    '-g', str(int(fps * 2)),  # GOP size ≈ 2 × fps for event clips
                ]

            # FFmpeg command with hardware encoding
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{w}x{h}',
                '-r', str(fps),
                '-i', '-',  # Read from stdin
                '-c:v', encoder,
            ] + encoder_opts + [
                '-pix_fmt', 'yuv420p',
                str(out_path)
            ]

            encoding_type = "hardware" if encoder in ['h264_nvenc', 'h264_v4l2m2m'] else "optimized software"
            self.logger.info(f"Attempting {encoding_type} encoding ({encoder}): {w}x{h} @ {fps}fps")
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Write frames to ffmpeg stdin
            pipe_broken = False
            for frame in frames:
                try:
                    proc.stdin.write(frame.tobytes())
                except (BrokenPipeError, IOError) as e:
                    self.logger.debug(f"Hardware encoding pipe broken during write: {e}")
                    pipe_broken = True
                    break

            try:
                if not pipe_broken and proc.stdin and not proc.stdin.closed:
                    proc.stdin.flush()
            except (BrokenPipeError, IOError, ValueError, AttributeError):
                pass  # Ignore flush errors
            
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except (BrokenPipeError, IOError, ValueError, AttributeError):
                pass  # Ignore close errors

            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                self.logger.warning("Hardware encoding timeout, process killed")

            success = proc.returncode == 0 and out_path.exists()

            if success:
                self.logger.info(f"✓ Hardware encoding succeeded: {out_path.name}")
            else:
                self.logger.warning(f"✗ Hardware encoding failed (returncode={proc.returncode})")
                if stderr:
                    # Log first 500 chars of error for debugging
                    error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                    self.logger.info(f"FFmpeg stderr: {error_msg}")

            return success

        except subprocess.TimeoutExpired:
            self.logger.error("Hardware encoding timeout (>10s)")
            return False
        except (BrokenPipeError, IOError, ValueError) as e:
            # Expected errors when encoder fails (pipe broken, flush on closed file, etc.)
            self.logger.debug(f"Hardware encoding pipe error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Hardware encoding unexpected error: {e}")
            return False

    def _encode_chunk_software(self, frames, out_path, fps):
        """Software encoding using OpenCV VideoWriter."""
        try:
            import cv2
            if not frames:
                return False

            h, w = frames[0].shape[:2]

            # Use H.264 codec for better compatibility with short clips
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
            out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

            if not out.isOpened():
                self.logger.error("Failed to open VideoWriter")
                return False

            for frame in frames:
                out.write(frame)

            out.release()
            success = out_path.exists() and out_path.stat().st_size > 0
            self.logger.info(f"✓ OpenCV encoding succeeded: {out_path.name}, size: {out_path.stat().st_size}")
            return success

=======
                self.logger.warning("⚠ GStreamer missing NVIDIA plugins")
                return False
>>>>>>> f2d60f60a9d8ce1d2713282b0f4b4be0f6ca9e7a
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
        """Start/stop hardware pipeline based on motion - ONE CONTINUOUS FILE per event"""
        self.logger.info("Starting pipeline manager (motion-triggered continuous recording)")
        
        pipeline_running = False
        output_dir = Path('tmp/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        current_output_file = None
        
        while self.running:
            try:
                # Check config for chunking enabled
                chunking_enabled = self.config.get('chunking_enabled', False)
                if not chunking_enabled:
                    time.sleep(1)
                    continue
                
                # Wait for motion
                if not self.motion_active:
                    # Stop pipeline if motion ended
                    if pipeline_running:
                        self.logger.info("⏹ Motion ended. Stopping pipeline...")
                        
                        # Stop the pipeline
                        if self.hw_pipeline:
                            self.hw_pipeline.stop()
                            self.hw_pipeline = None
                        pipeline_running = False
                        
                        # Give GStreamer time to finalize the file
                        time.sleep(2)
                        
                        # Upload the complete motion event file
                        if current_output_file and Path(current_output_file).exists():
                            file_size = Path(current_output_file).stat().st_size
                            if file_size > 100000:  # Valid file
                                self._queue_chunk_upload(Path(current_output_file))
                                self.logger.info(f"✓ Motion event saved: {current_output_file} ({file_size} bytes)")
                            else:
                                self.logger.warning(f"⚠ File too small: {current_output_file} ({file_size} bytes)")
                        
                        current_output_file = None
                    
                    time.sleep(0.2)
                    continue
                
                # Motion is active - start pipeline for this event
                if not pipeline_running:
                    if self._gst_available and self.config.get('use_hardware_pipeline', True):
                        # Generate unique filename for this motion event
                        timestamp = int(time.time())
                        current_output_file = str(output_dir / f'{self.stream_id}_{timestamp}.mp4')
                        
                        self.logger.info(f"🎬 Motion detected! Recording to: {current_output_file}")
                        
                        # Start hardware pipeline with specific output file
                        self.hw_pipeline = HardwarePipeline(
                            self.stream_id, 
                            self.rtsp_url, 
                            self.config,
                            output_file=current_output_file
                        )
                        self.hw_pipeline.start()
                        pipeline_running = True
                        self.logger.info("✓ Hardware pipeline recording continuous motion event")
                
                time.sleep(0.5)
                
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
<<<<<<< HEAD
            self.logger.error(f"Failed to log motion event: {e}")

    def _get_target_bitrate(self):
        if self._low_quality:
            return self.low_bitrate
        if not self.motion_active:
            return self.low_bitrate
        return self.default_bitrate

    def _get_target_fps(self):
        """Return target FPS based on motion state.

        Now returns fixed high FPS to avoid pipeline restarts.
        Motion inactivity is handled by frame dropping at capture level.
        """
        return int(self.config.get('motion_high_fps', 25))

    def _build_ffmpeg_command(self):
        # Build ffmpeg command with dynamic FPS and bitrate
        target_fps = self._get_target_fps()
        target_bitrate = self._get_target_bitrate()
        
        # Output to local file or pipe (no SRT)
        cmd = (
            f"ffmpeg -re -rtsp_transport tcp -i {shlex.quote(self.rtsp_url)} "
            f"-r {target_fps} -c:v libx264 -preset ultrafast -b:v {target_bitrate} "
            f"-maxrate {target_bitrate} -bufsize {target_bitrate * 2} "
            f"-g {target_fps * 2} -f mpegts pipe:1"
        )
        return shlex.split(cmd)

    def _start_ffmpeg(self):
        # Ensure ffmpeg is available before attempting to start
        if not Streamer._ffmpeg_path:
            # warn once per-instance to avoid log spam
            if not self._ffmpeg_warned:
                print("Failed to start ffmpeg pipeline: ffmpeg not found on PATH."
                      " Please install ffmpeg (e.g. Chocolatey on Windows) and ensure it's available in your PATH.")
                self._ffmpeg_warned = True
            # Do not attempt to start; watcher thread will start pipeline when ffmpeg appears
            self.proc = None
            return

        args = self._build_ffmpeg_command()
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print(f"Failed to start ffmpeg pipeline: {e}")
            self.proc = None

    def _ffmpeg_watcher(self):
        """Background watcher: poll for ffmpeg on PATH and start pipeline when found.

        This avoids repeated error spam at startup and allows admins to install
        ffmpeg later without restarting the whole agent.
        """
        # quick-return if ffmpeg already present
        if Streamer._ffmpeg_path:
            return
        try:
            while self.running and not Streamer._ffmpeg_path:
                path = shutil.which('ffmpeg')
                if path:
                    Streamer._ffmpeg_path = path
                    print(f"ffmpeg detected at {path}; starting pipeline for stream {self.stream_id}")
                    # reset warning flag now that ffmpeg is available
                    self._ffmpeg_warned = False
                    # start the pipeline
                    self._start_ffmpeg()
                    break
                time.sleep(5)
        except Exception:
            # watcher should never crash the program
            pass

    def _restart_pipeline(self):
        try:
            if hasattr(self, 'proc') and self.proc:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except Exception:
                    self.proc.kill()
        except Exception:
            pass
        self._start_ffmpeg()
=======
            self.logger.error(f"Failed to log event: {e}")
>>>>>>> f2d60f60a9d8ce1d2713282b0f4b4be0f6ca9e7a

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

    def cleanup_logger(self):
        """Close all logger handlers to release file locks"""
        if self.logger:
            handlers = self.logger.handlers[:]
            for handler in handlers:
                handler.close()
                self.logger.removeHandler(handler)

<<<<<<< HEAD
        if use_hw_decode:
            # Try hardware-accelerated FFmpeg decode first
            self.logger.info(f"Starting capture loop with hardware decoding for {self.rtsp_url}")
            success = self._capture_loop_hw_decode()
            if success:
                return
            self.logger.warning("Hardware decode failed, falling back to OpenCV")

        # Fallback to OpenCV software decoding
        self.logger.info(f"Starting capture loop (software decode) for {self.rtsp_url}")
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
            return

        # Configure capture buffer to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.logger.info("RTSP stream opened successfully")
        frame_count = 0
        last_frame_time = time.time()
        target_interval = 0.1  # 10 FPS

        while self.running:
            ret, frame = cap.read()
            if not ret:
                self.logger.warning("Failed to read frame, retrying...")
                time.sleep(0.5)
                continue

            frame_count += 1
            if frame_count % 100 == 0:  # Log every 100 frames
                self.logger.info(f"Captured {frame_count} frames")

            try:
                # Only queue frames when motion is active or during cooldown
                # This implements frame dropping for motion inactivity instead of FPS changes
                if self.motion_active and not self.frame_queue.full():
                    self.frame_queue.put(frame, block=False)
            except Exception:
                pass

            # Dynamic sleep to maintain target FPS without wasting CPU
            elapsed = time.time() - last_frame_time
            sleep_time = max(0, target_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
            last_frame_time = time.time()

        cap.release()
        self.logger.info("Capture loop ended")

    def _capture_loop_nvdec(self):
        """NVIDIA hardware-accelerated RTSP capture using NVDEC (Jetson Orin)."""
        import cv2
        import numpy as np

    def _capture_loop_nvdec(self):
        """NVIDIA hardware-accelerated RTSP capture using NVDEC (Jetson Orin)."""
        import cv2
        import numpy as np

        try:
            # FFmpeg command with NVDEC hardware decoding for Jetson
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-hwaccel', 'cuda',        # Enable CUDA hardware acceleration
                '-hwaccel_device', '0',    # Use GPU device 0
                '-c:v', 'h264_cuvid',      # Use NVIDIA CUVID decoder
                '-i', self.rtsp_url,
                '-vf', 'fps=10',  # Limit FPS only, keep original resolution
                '-f', 'rawvideo',
                '-pix_fmt', 'bgr24',
                'pipe:1'
            ]

            self.logger.info("Starting hardware-accelerated decode pipeline")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)

            frame_count = 0
            last_frame_time = time.time()
            target_interval = 0.1
            width, height = None, None

            # Try to detect resolution from stderr output
            import threading
            resolution_detected = threading.Event()
            
            def read_stderr():
                for line in proc.stderr:
                    decoded = line.decode('utf-8', errors='ignore')
                    if 'Stream #' in decoded and 'Video:' in decoded:
                        import re
                        match = re.search(r'(\d{3,4})x(\d{3,4})', decoded)
                        if match:
                            nonlocal width, height
                            width, height = int(match.group(1)), int(match.group(2))
                            self.logger.info(f"Detected resolution: {width}x{height}")
                            resolution_detected.set()

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Wait up to 3 seconds for resolution detection
            if not resolution_detected.wait(timeout=3.0):
                # Default to common resolution
                width, height = 1920, 1080
                self.logger.warning(f"Could not detect resolution, using default {width}x{height}")
            else:
                self.logger.info(f"Successfully detected resolution: {width}x{height}")

            frame_size = width * height * 3  # BGR24 = 3 bytes per pixel

            while self.running:
                raw_frame = proc.stdout.read(frame_size)

                if len(raw_frame) != frame_size:
                    # Try to auto-detect resolution from actual frame size
                    if len(raw_frame) > 0 and len(raw_frame) % 3 == 0:
                        pixel_count = len(raw_frame) // 3
                        # Common resolutions
                        common_res = [(1920, 1080), (2304, 1296), (1280, 720), (3840, 2160), (2560, 1440)]
                        for w, h in common_res:
                            if w * h == pixel_count:
                                width, height = w, h
                                frame_size = len(raw_frame)
                                self.logger.info(f"Auto-corrected resolution from frame size: {width}x{height}")
                                # Continue with current frame
                                break
                    
                    if len(raw_frame) != frame_size:
                        self.logger.warning("Incomplete frame or stream ended")
                        break

                # Convert raw bytes to numpy array
                frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))

                frame_count += 1
                if frame_count % 100 == 0:
                    self.logger.info(f"Captured {frame_count} frames (NVDEC)")

                try:
                    # Only queue frames when motion is active or during cooldown
                    if self.motion_active and not self.frame_queue.full():
                        self.frame_queue.put(frame, block=False)
                except Exception:
                    pass

                # Dynamic sleep to maintain target FPS
                elapsed = time.time() - last_frame_time
                sleep_time = max(0, target_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_frame_time = time.time()

            proc.terminate()
            try:
                proc.wait(timeout=3)
            except:
                proc.kill()

            self.logger.info("NVDEC decode capture loop ended successfully")
            return True

        except Exception as e:
            self.logger.error(f"NVDEC decode error: {e}")
            try:
                proc.terminate()
            except:
                pass
            return False

    def _capture_loop_hw_decode(self):
        """Hardware-accelerated RTSP capture using GStreamer pipeline on Jetson."""
        import cv2
        import numpy as np

        try:
            # Check if we're on Jetson
            is_jetson = os.path.exists('/etc/nv_tegra_release') or os.path.exists('/sys/module/tegra_fuse')
            
            if not is_jetson:
                self.logger.warning("Hardware decode only supported on Jetson, falling back")
                return False

            # GStreamer pipeline for RTSP hardware decoding on Jetson Orin
            # This uses NVIDIA's hardware decoder (NVDEC) via nvv4l2decoder
            gst_pipeline = (
                f"rtspsrc location={self.rtsp_url} latency=0 ! "
                "rtph264depay ! h264parse ! "
                "nvv4l2decoder ! nvvidconv ! "
                "video/x-raw,format=BGRx ! videoconvert ! "
                "video/x-raw,format=BGR ! appsink"
            )

            self.logger.info("Starting hardware-accelerated decode pipeline with GStreamer")
            
            # Set OpenCV to use GStreamer backend
            cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            
            if not cap.isOpened():
                self.logger.error("Failed to open GStreamer pipeline for hardware decode")
                return False

            # Configure buffer size for low latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.logger.info("GStreamer hardware decode pipeline opened successfully")
            frame_count = 0
            last_frame_time = time.time()
            target_interval = 0.1  # 10 FPS

            success = True
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame from hardware decode pipeline")
                    success = False
                    break

                frame_count += 1
                if frame_count % 100 == 0:  # Log every 100 frames
                    self.logger.info(f"Captured {frame_count} frames (HW decode)")

                try:
                    # Only queue frames when motion is active or during cooldown
                    if self.motion_active and not self.frame_queue.full():
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
            self.logger.info("Hardware decode capture loop ended")
            return success

        except Exception as e:
            self.logger.error(f"Hardware decode error: {e}")
            return False

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
                # self.logger.debug("No frames in queue, motion inactive")
                time.sleep(0.5)
                continue
            
            # Get raw motion detection result (before cooldown)
            motion = self.detector.detect(frame)
            
            # Track motion stats for debugging
            if motion:
                motion_frame_count += 1
                no_motion_frame_count = 0
            else:
                no_motion_frame_count += 1
                motion_frame_count = 0
            
            # Log when motion starts/stops being detected (not cooldown)
            if motion_frame_count == 1:
                self.logger.info("Motion STARTED being detected")
            elif no_motion_frame_count == 1:
                self.logger.info("Motion STOPPED being detected (cooldown may still be active)")
            
            # Only trigger pipeline restart when motion state actually changes
            if motion != last_motion_state:
                self.motion_active = motion
                target_bitrate = self._get_target_bitrate()
                # FPS is now fixed, only restart on bitrate changes
                fixed_fps = self._get_target_fps()
                
                if last_bitrate is None:
                    last_bitrate = target_bitrate
                    # Initial state - start pipeline at fixed high FPS
                    self.logger.info(f"Initial state: Motion={motion}, Fixed FPS {fixed_fps}, Bitrate {target_bitrate}")
                    self._log_motion_event("MOTION" if motion else "IDLE", fixed_fps)
                    self._restart_pipeline()
                elif target_bitrate != last_bitrate:
                    # Only restart on bitrate changes (network adaptation), not FPS changes
                    status = "Motion ACTIVE" if motion else "Motion INACTIVE"
                    self.logger.info(f"{status}: Bitrate {last_bitrate}->{target_bitrate} (fixed FPS {fixed_fps}); restarting pipeline")
                    self._log_motion_event("MOTION" if motion else "IDLE", fixed_fps)
                    self._restart_pipeline()
                    last_bitrate = target_bitrate
                
                last_motion_state = motion
            
            time.sleep(0.05)
        self.logger.info("Motion detection loop ended")

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Enable/disable low-quality mode for all streamers with hysteresis.

        Network adaptation hysteresis prevents immediate quality switching on
        bandwidth jitter. Requires stable conditions for hold_time before applying changes.
        """
        with cls._lock:
            current_time = time.time()

            if enabled and not cls._pending_low_quality:
                # Requesting low quality - start hysteresis timer
                cls._pending_low_quality = True
                cls._network_quality_change_time = current_time
                cls._logger.info(f"Network quality degradation detected, waiting {cls._network_hysteresis_hold_time}s before switching to low quality")
                # Start background thread to apply change after hold time
                threading.Thread(target=cls._apply_pending_quality_change, args=(enabled,), daemon=True).start()

            elif not enabled and cls._pending_low_quality:
                # Requesting recovery - start hysteresis timer
                cls._pending_low_quality = False
                cls._network_quality_change_time = current_time
                cls._logger.info(f"Network quality recovery detected, waiting {cls._network_hysteresis_hold_time}s before switching to high quality")
                # Start background thread to apply change after hold time
                threading.Thread(target=cls._apply_pending_quality_change, args=(enabled,), daemon=True).start()

    @classmethod
    def _apply_pending_quality_change(cls, enabled: bool):
        """Apply pending quality change after hysteresis hold time."""
        hold_time = cls._network_hysteresis_hold_time

        # Wait for hold time
        time.sleep(hold_time)

        with cls._lock:
            # Check if the request is still pending (no conflicting requests during hold time)
            if (enabled and cls._pending_low_quality) or (not enabled and not cls._pending_low_quality):
                cls._low_quality = enabled
                quality = "LOW" if enabled else "HIGH"
                cls._logger.info(f"Network adaptation hysteresis complete: switching to {quality} quality")

                # Restart pipelines for all instances
                for inst in list(cls._instances):
                    try:
                        inst._restart_pipeline()
                    except Exception:
                        # Individual restart failures should not block others
                        pass
            else:
                cls._logger.info("Network adaptation hysteresis cancelled: conflicting request received during hold time")
=======
        # Also cleanup hardware pipeline logger
        if self.hw_pipeline and hasattr(self.hw_pipeline, 'cleanup_logger'):
            self.hw_pipeline.cleanup_logger()

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Set low quality mode"""
        with cls._lock:
            cls._low_quality = enabled
>>>>>>> f2d60f60a9d8ce1d2713282b0f4b4be0f6ca9e7a

    @classmethod
    def restart_all(cls):
        """Restart all streamers"""
        for inst in list(cls._instances):
            try:
                inst.logger.info("Config changed")
            except:
                pass