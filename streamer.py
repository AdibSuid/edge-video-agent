"""
Minimal streamer implementation used by tests and runtime.

This file intentionally keeps a small surface area and consistent 4-space
indentation to avoid previous IndentationError issues. Behavior is a subset
of the full agent: it supports SRT target construction and a simple
dynamic-bitrate policy used by the rest of the codebase.
"""

import subprocess
import shlex
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

        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._motion_loop, daemon=True).start()
        # do not start external processes in constructor for test-safety

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
        args = self._build_ffmpeg_command()
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print(f"Failed to start ffmpeg pipeline: {e}")

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

    def set_low_quality(self, enabled: bool):
        with self._lock:
            self._low_quality = enabled
            for inst in list(self._instances):
                inst._restart_pipeline()

    @classmethod
    def restart_all(cls):
        for inst in list(cls._instances):
            inst._restart_pipeline()
