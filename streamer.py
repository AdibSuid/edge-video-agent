"""
Minimal streamer implementation used by tests and runtime.

This file intentionally keeps a small surface area and consistent 4-space
indentation to avoid previous IndentationError issues. Behavior is a subset
of the full agent: it supports SRT target construction and a simple
dynamic-bitrate policy used by the rest of the codebase.
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
import os

# Try to import CUDA motion detector, fallback to CPU version
try:
    from motion_detector_cuda import MotionDetectorCUDA as MotionDetector
    CUDA_AVAILABLE = True
except ImportError:
    from motion_detector import MotionDetector
    CUDA_AVAILABLE = False


class Streamer:
    """Compact RTSP streamer with dynamic bitrate.

    Public methods used elsewhere: set_low_quality(enabled), restart_all()
    """

    _instances = []
    _low_quality = False
    _lock = threading.Lock()
    # path to ffmpeg if available on PATH (updated by autodetect)
    _ffmpeg_path = shutil.which('ffmpeg')

    def __init__(self, rtsp_url, config, stream_id):
        self.rtsp_url = rtsp_url
        self.stream_id = stream_id
        self.config = config
        self.motion_active = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True

        # Initialize logger FIRST before using it
        self.logger = self._setup_logger()

        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=config.get('motion_zones', []),
            cooldown=config.get('motion_cooldown', 10),
            detection_scale=config.get('motion_detection_scale', 0.25),
            blur_kernel=config.get('motion_blur_kernel', 5),
            frame_skip=config.get('motion_frame_skip', 2),
        )
        
        # Log motion detector type
        if CUDA_AVAILABLE:
            try:
                detector_info = self.detector.get_info()
                self.logger.info(f"Using CUDA-accelerated motion detector: {detector_info}")
            except:
                self.logger.info("Using motion detector (CUDA status unknown)")
        else:
            self.logger.info("Using CPU motion detector")

        self.default_bitrate = int(config.get('default_bitrate', 2000000))
        self.low_bitrate = int(config.get('low_bitrate', max(400000, self.default_bitrate // 4)))

        self._instances.append(self)

        # per-instance flag to avoid repeated missing-ffmpeg spam
        self._ffmpeg_warned = False

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
                            # Remove any partial file from failed hardware encoding
                            if out_path.exists():
                                try:
                                    out_path.unlink()
                                except Exception as e:
                                    self.logger.debug(f"Could not remove partial file: {e}")
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
        """
        Encode video chunk using GStreamer with nvv4l2h264enc (community standard).

        This is the NVIDIA-recommended approach for Jetson platforms using GStreamer
        with V4L2 hardware-accelerated encoding. Supports both JetPack 4.x and 5.x.
        """
        try:
            import cv2
            import subprocess

            if not frames:
                return False

            h, w = frames[0].shape[:2]
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if we're on Jetson
            is_jetson = os.path.exists('/etc/nv_tegra_release') or os.path.exists('/sys/module/tegra_fuse')

            if not is_jetson:
                self.logger.warning("Hardware encoding only supported on Jetson, using software fallback")
                return False

            # Build GStreamer pipeline for hardware encoding (community standard)
            # Uses nvv4l2h264enc which works on both JetPack 4.x and 5.x
            gst_cmd = [
                'gst-launch-1.0',
                '-e',  # Send EOS on interrupt
                'fdsrc', '!',
                f'video/x-raw,format=BGR,width={w},height={h},framerate={fps}/1', '!',
                'videoconvert', '!',
                'video/x-raw,format=I420', '!',
                'nvv4l2h264enc',
                'maxperf-enable=true',        # Enable maximum performance mode (lowest latency)
                'bitrate=2000000',             # 2 Mbps target bitrate
                'preset-level=1',              # 0=Slow, 1=Medium, 2=Fast, 3=UltraFast
                'insert-sps-pps=true',         # Insert SPS/PPS at every IDR frame
                'idrinterval=30', '!',         # IDR frame interval (keyframe every 30 frames)
                'h264parse', '!',
                'qtmux', '!',
                f'filesink location={out_path}'
            ]

            self.logger.info(f"Encoding with nvv4l2h264enc (GStreamer): {w}x{h} @ {fps}fps")

            # Start GStreamer subprocess
            proc = subprocess.Popen(
                gst_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )

            # Write frames to GStreamer stdin
            frames_written = 0
            for frame in frames:
                try:
                    if proc.stdin and not proc.stdin.closed:
                        proc.stdin.write(frame.tobytes())
                        frames_written += 1
                    else:
                        self.logger.debug("GStreamer stdin closed prematurely")
                        break
                except (BrokenPipeError, IOError) as e:
                    self.logger.debug(f"GStreamer pipe broken: {e}")
                    break

            self.logger.debug(f"Wrote {frames_written} frames to GStreamer encoder")

            # Close stdin and wait for encoding to complete
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.flush()
                    proc.stdin.close()
            except Exception as e:
                self.logger.debug(f"Error closing stdin: {e}")
                pass

            # Wait for GStreamer to finish encoding
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                self.logger.warning("GStreamer encoding timeout, process killed")

            # Check success
            success = proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0

            if success:
                file_size = out_path.stat().st_size
                self.logger.info(f"✓ GStreamer hardware encoding succeeded: {out_path.name} "
                               f"({file_size} bytes, {frames_written} frames)")
            else:
                self.logger.warning(f"✗ GStreamer hardware encoding failed (returncode={proc.returncode})")
                if stderr:
                    error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                    self.logger.debug(f"GStreamer stderr: {error_msg}")
                # Clean up partial file
                if out_path.exists():
                    try:
                        out_path.unlink()
                    except Exception:
                        pass

            return success

        except Exception as e:
            self.logger.error(f"GStreamer hardware encoding error: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    def _encode_chunk_software(self, frames, out_path, fps):
        """Software encoding using OpenCV VideoWriter."""
        try:
            import cv2
            if not frames:
                return False

            h, w = frames[0].shape[:2]

            # Ensure output directory exists
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Use OpenCV VideoWriter with MP4V codec (works on most systems)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

            if not out.isOpened():
                self.logger.error("Failed to open VideoWriter")
                return False

            frames_written = 0
            for frame in frames:
                try:
                    out.write(frame)
                    frames_written += 1
                except Exception as e:
                    self.logger.error(f"Error writing frame {frames_written}: {e}")
                    break

            # Properly release the writer
            try:
                out.release()
            except Exception as e:
                self.logger.debug(f"Error releasing VideoWriter: {e}")

            # Check if file was created and has content
            success = out_path.exists() and out_path.stat().st_size > 0
            if success:
                self.logger.info(f"✓ OpenCV encoding succeeded: {out_path.name}, size: {out_path.stat().st_size}, frames: {frames_written}")
            else:
                self.logger.error(f"✗ OpenCV encoding failed: file not created or empty")
                # Clean up empty file
                if out_path.exists():
                    try:
                        out_path.unlink()
                    except Exception as e:
                        self.logger.debug(f"Could not remove empty file: {e}")

            return success

        except Exception as e:
            self.logger.error(f"OpenCV encoding error: {e}")
            # Clean up any partial file
            if out_path.exists():
                try:
                    out_path.unlink()
                except Exception as cleanup_error:
                    self.logger.debug(f"Could not cleanup partial file: {cleanup_error}")
            return False

    def _upload_chunk_to_cloud(self, chunk_path, chunk_id, ts_start, ts_end):
        """Upload chunk to cloud server with authentication."""
        try:
            from cloud_uploader import cloud_uploader
            
            if cloud_uploader and cloud_uploader.enabled:
                # Get camera name from config for stream_id
                stream_name = self.config.get('name', self.stream_id)
                
                # Queue for upload (non-blocking)
                cloud_uploader.queue_chunk(chunk_path, stream_name, ts_start, ts_end)
                self.logger.info(f"Queued chunk for cloud upload: {chunk_path.name}")
            else:
                self.logger.debug(f"Cloud upload disabled or not configured")
        except Exception as e:
            self.logger.error(f"Error queuing chunk for upload: {e}")

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
        """Return target FPS based on motion state and config.

        Uses `motion_high_fps` and `motion_low_fps` values from config with
        sensible defaults (25/1).
        """
        if self.motion_active:
            return int(self.config.get('motion_high_fps', 25))
        return int(self.config.get('motion_low_fps', 1))

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
            # If detector doesn't support update_settings, ignore
            pass
        # Restart pipeline to pick up bitrate/resolution changes
        try:
            self._restart_pipeline()
        except Exception:
            pass

    def stop(self):
        """Stop the streamer gracefully: stop threads, terminate process, and unregister."""
        # mark as not running so threads exit
        self.running = False

        # terminate ffmpeg process if running
        try:
            if hasattr(self, 'proc') and self.proc:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=3)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass

        # remove from instances list
        try:
            if self in self._instances:
                self._instances.remove(self)
        except Exception:
            pass

    def _capture_loop(self):
        # lightweight capture loop used for motion detection
        import cv2
        import numpy as np

        use_hw_decode = self.config.get('use_hardware_decode', True)
        is_jetson = os.path.exists('/etc/nv_tegra_release') or os.path.exists('/sys/module/tegra_fuse')

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
                if not self.frame_queue.full():
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
                target_fps = self._get_target_fps()
                
                if last_bitrate is None:
                    last_bitrate = target_bitrate
                    last_fps = target_fps
                    # Initial state - start pipeline
                    self.logger.info(f"Initial state: Motion={motion}, FPS {target_fps}, Bitrate {target_bitrate}")
                    self._log_motion_event("MOTION" if motion else "IDLE", target_fps)
                    self._restart_pipeline()
                elif target_bitrate != last_bitrate or target_fps != last_fps:
                    status = "Motion ACTIVE (high FPS)" if motion else "Motion INACTIVE (low FPS)"
                    self.logger.info(f"{status}: FPS {last_fps}->{target_fps}, Bitrate {last_bitrate}->{target_bitrate}; restarting pipeline")
                    self._log_motion_event("MOTION" if motion else "IDLE", target_fps)
                    self._restart_pipeline()
                    last_bitrate = target_bitrate
                    last_fps = target_fps
                
                last_motion_state = motion
            
            time.sleep(0.05)
        self.logger.info("Motion detection loop ended")

    @classmethod
    def set_low_quality(cls, enabled: bool):
        """Enable/disable low-quality mode for all streamers.

        This is a classmethod to match calls like `Streamer.set_low_quality(True)`
        made elsewhere in the codebase.
        """
        with cls._lock:
            cls._low_quality = enabled
            for inst in list(cls._instances):
                try:
                    inst._restart_pipeline()
                except Exception:
                    # Individual restart failures should not block others
                    pass

    @classmethod
    def restart_all(cls):
        for inst in list(cls._instances):
            inst._restart_pipeline()
