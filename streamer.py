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

from motion_detector import MotionDetector


class Streamer:
    """Compact RTSP->SRT streamer with dynamic bitrate.

    Public methods used elsewhere: set_low_quality(enabled), restart_all()
    """

    _instances = []
    _low_quality = False
    _lock = threading.Lock()
    # path to ffmpeg if available on PATH (updated by autodetect)
    _ffmpeg_path = shutil.which('ffmpeg')

    def __init__(self, rtsp_url, srt_url, passphrase, config, stream_id):
        self.rtsp_url = rtsp_url
        srt_mode = config.get('srt_mode')
        srt_params = config.get('srt_params') or {}
        q = [f"passphrase={passphrase}"]
        if srt_mode:
            q.append(f"mode={srt_mode}")
        for k, v in srt_params.items():
            q.append(f"{k}={v}")
        self.srt_target = srt_url + ('?' + '&'.join(q) if q else '')

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
                        frames.append(frame)
                    except queue.Empty:
                        pass
                    time.sleep(1.0 / max(1, chunk_fps))
                if frames:
                    # Save chunk to file
                    chunk_id = str(uuid.uuid4())[:8]
                    out_dir = Path('tmp/chunks')
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / f"{self.stream_id}_{chunk_id}.mp4"
                    h, w = frames[0].shape[:2]
                    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'mp4v'), chunk_fps, (w, h))
                    for f in frames:
                        writer.write(f)
                    writer.release()
                    self.logger.info(f"Chunk saved: {out_path}")
                    # Upload to cloud (template)
                    self._upload_chunk_to_cloud(out_path, chunk_id)
            except Exception as e:
                self.logger.error(f"Chunking error: {e}")
            time.sleep(0.5)

    def _upload_chunk_to_cloud(self, chunk_path, chunk_id):
        """Draft/template for cloud upload: S3 + SQS."""
        # Replace with real S3/SQS integration when ready
        # Example metadata: stream_id, chunk_id, s3_key
        print(f"[UPLOAD TEMPLATE] Would upload {chunk_path} to S3 and send SQS msg: stream_id={self.stream_id}, chunk_id={chunk_id}")
        self.logger.info(f"[UPLOAD TEMPLATE] Would upload {chunk_path} to S3 and send SQS msg: stream_id={self.stream_id}, chunk_id={chunk_id}")

    def _setup_logger(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger(f'streamer-{self.stream_id}')
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_dir / f'{self.stream_id}.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(fh)
        return logger

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
        bitrate = self._get_target_bitrate()
        if bitrate >= 1000000:
            b_str = f"{bitrate // 1000000}M"
        else:
            b_str = f"{bitrate // 1000}k"
        cmd = (
            f"ffmpeg -rtsp_transport tcp -i {shlex.quote(self.rtsp_url)} -c:v libx264 "
            f"-preset superfast -tune zerolatency -b:v {b_str} -f mpegts {shlex.quote(self.srt_target)}"
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
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            return
        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue
            try:
                if not self.frame_queue.full():
                    self.frame_queue.put(frame, block=False)
            except Exception:
                pass
            time.sleep(0.01)

    def _motion_loop(self):
        last_bitrate = None
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1)
            except queue.Empty:
                self.motion_active = False
                time.sleep(0.5)
                continue
            motion = self.detector.detect(frame)
            self.motion_active = motion
            target = self._get_target_bitrate()
            if last_bitrate is None:
                last_bitrate = target
            if target != last_bitrate:
                self.logger.info(f"Bitrate change {last_bitrate}->{target}; restarting pipeline")
                self._restart_pipeline()
                last_bitrate = target
            time.sleep(0.05)

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
