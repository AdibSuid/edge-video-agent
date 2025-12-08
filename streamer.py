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

from motion_detector import MotionDetector


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

        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=config.get('motion_zones', []),
            cooldown=config.get('motion_cooldown', 10),
        )

        self.default_bitrate = int(config.get('default_bitrate', 2000000))
        self.low_bitrate = int(config.get('low_bitrate', max(400000, self.default_bitrate // 4)))

        self.logger = self._setup_logger()

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
                    # Save chunk to file using hardware encoding if available
                    chunk_id = str(uuid.uuid4())[:8]
                    ts_start = int(start_time)
                    ts_end = int(time.time())
                    out_dir = Path('tmp/chunks')
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"{self.stream_id}_{chunk_id}.mp4"

                    # Try hardware encoding first, fallback to software
                    success = self._encode_chunk_hardware(frames, out_path, chunk_fps)
                    if not success:
                        self.logger.warning("Hardware encoding failed, falling back to software encoding")
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
        """Encode video chunk using hardware encoder (h264_v4l2m2m)."""
        try:
            import cv2
            if not frames:
                return False

            h, w = frames[0].shape[:2]

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
                '-c:v', 'h264_v4l2m2m',  # Hardware encoder
                '-num_output_buffers', '32',
                '-num_capture_buffers', '16',
                '-b:v', '1M',  # 1 Mbps bitrate for chunks
                '-pix_fmt', 'yuv420p',
                str(out_path)
            ]

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Write frames to ffmpeg stdin
            for frame in frames:
                try:
                    proc.stdin.write(frame.tobytes())
                except BrokenPipeError:
                    break

            proc.stdin.close()
            proc.wait(timeout=10)

            return proc.returncode == 0 and out_path.exists()

        except Exception as e:
            self.logger.error(f"Hardware encoding error: {e}")
            return False

    def _encode_chunk_software(self, frames, out_path, fps):
        """Fallback software encoding using cv2.VideoWriter."""
        try:
            import cv2
            if not frames:
                return False

            h, w = frames[0].shape[:2]
            writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

            for frame in frames:
                writer.write(frame)

            writer.release()
            return out_path.exists()

        except Exception as e:
            self.logger.error(f"Software encoding error: {e}")
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
        self.logger.info(f"Starting capture loop for {self.rtsp_url}")
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            self.logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
            return
        self.logger.info("RTSP stream opened successfully")
        frame_count = 0
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
            # Limit to ~10 FPS for motion detection (reduces CPU usage)
            time.sleep(0.1)
        cap.release()
        self.logger.info("Capture loop ended")

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
