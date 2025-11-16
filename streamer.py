# streamer.py
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    HAVE_GST = True
except Exception:
    Gst = None
    GLib = None
    HAVE_GST = False
    print("Warning: GStreamer (gi) not available; falling back to ffmpeg subprocess pipeline")
import subprocess
import shlex
import cv2
import threading
import time
import queue
import logging
from pathlib import Path
from motion_detector import MotionDetector

if HAVE_GST:
    try:
        Gst.init(None)
    except Exception:
        print("Warning: Gst.init failed; continuing with ffmpeg fallback")
        HAVE_GST = False

class Streamer:
    """
    Handles RTSP to SRT streaming with motion-triggered adaptive FPS
    """
    _instances = []
    _low_quality = False
    _lock = threading.Lock()

    def __init__(self, rtsp_url, srt_url, passphrase, config, stream_id):
        """
        Initialize streamer
        
        Args:
            rtsp_url: Source RTSP URL
            srt_url: Destination SRT URL
            passphrase: AES encryption passphrase
            config: Configuration dictionary
            stream_id: Unique stream identifier
        """
        self.rtsp_url = rtsp_url
        self.srt_url = f"{srt_url}?passphrase={passphrase}"
        self.config = config
        self.stream_id = stream_id
        self.pipeline = None
        self.main_loop = None
        self.motion_active = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True
        
        # Initialize motion detector
        self.detector = MotionDetector(
            sensitivity=config.get('motion_sensitivity', 25),
            min_area=config.get('motion_min_area', 500),
            zones=config.get('motion_zones', []),
            cooldown=config.get('motion_cooldown', 10)
        )
        
        # Setup logging
        self.logger = self._setup_logger()
        
        # Register instance
        self._instances.append(self)

        # Start threads
        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._motion_loop, daemon=True).start()
        self._start_pipeline()

    def _setup_logger(self):
        """Setup motion event logger"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger(f"motion_{self.stream_id}")
        logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_dir / f"motion_{self.stream_id}.log")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(fh)
        
        return logger

    def _capture_loop(self):
        """Capture frames from RTSP for motion detection"""
        while self.running:
            try:
                cap = cv2.VideoCapture(self.rtsp_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                
                while self.running:
                    ret, frame = cap.read()
                    if ret:
                        # Only keep latest frame
                        if not self.frame_queue.full():
                            self.frame_queue.put(frame.copy())
                    else:
                        print(f"[{self.stream_id}] Failed to read frame, reconnecting...")
                        break
                    time.sleep(0.033)  # ~30fps sampling
                    
                cap.release()
            except Exception as e:
                print(f"[{self.stream_id}] Capture error: {e}")
                time.sleep(5)

    def _motion_loop(self):
        """Motion detection loop"""
        while self.running:
            try:
                if not self.frame_queue.empty():
                    frame = self.frame_queue.get()
                    motion = self.detector.detect(frame)
                    
                    # State change detected
                    if motion != self.motion_active:
                        self.motion_active = motion
                        self._restart_pipeline()
                        
                        status = "MOTION" if motion else "IDLE"
                        fps = self._get_target_fps()
                        self.logger.info(f"{status} - FPS: {fps}")
                        
                        # Log event for web UI
                        self._log_event(status, fps)
                        
                time.sleep(0.1)
            except Exception as e:
                print(f"[{self.stream_id}] Motion loop error: {e}")
                time.sleep(1)

    def _get_target_fps(self):
        """Get target FPS based on motion state"""
        if self.motion_active:
            return self.config.get('motion_high_fps', 25)
        return self.config.get('motion_low_fps', 1)

    def _get_resolution(self):
        """Get target resolution based on network quality"""
        if self._low_quality:
            return self.config.get('low_resolution', '640x360')
        return self.config.get('normal_resolution', '1280x720')

    def _build_pipeline(self):
        """Build GStreamer pipeline with current settings"""
        fps = self._get_target_fps()
        w, h = map(int, self._get_resolution().split('x'))
        
        pipeline_str = (
            f'rtspsrc location="{self.rtsp_url}" latency=0 ! '
            'rtph264depay ! h264parse ! avdec_h264 ! '
            'videoconvert ! videoscale ! '
            f'video/x-raw,width={w},height={h} ! '
            f'videorate ! video/x-raw,framerate={fps}/1 ! '
            'x264enc bitrate=800 tune=zerolatency speed-preset=ultrafast ! '
            'mpegtsmux ! '
            f'srtsink uri="{self.srt_url}"'
        )
        
        if HAVE_GST:
            try:
                return Gst.parse_launch(pipeline_str)
            except Exception as e:
                print(f"[{self.stream_id}] Pipeline build error: {e}")
                raise
        # If GStreamer not available, return the ffmpeg command string
        return pipeline_str

    def _build_ffmpeg_command(self):
        """Construct an ffmpeg command line equivalent to the GStreamer pipeline"""
        fps = self._get_target_fps()
        w, h = map(int, self._get_resolution().split('x'))

        # Use -rtsp_transport tcp for reliability on many cameras
        cmd = (
            f"ffmpeg -rtsp_transport tcp -hide_banner -loglevel info -y -i \"{self.rtsp_url}\" "
            f"-vf scale={w}:{h} -r {fps} -c:v libx264 -preset ultrafast -tune zerolatency "
            f"-b:v {self.config.get('default_bitrate', 2000000)} -f mpegts \"{self.srt_url}\""
        )
        return cmd

    def _start_pipeline(self):
        """Start pipeline in separate thread using GStreamer or ffmpeg fallback"""
        if HAVE_GST:
            threading.Thread(target=self._run_pipeline, daemon=True).start()
        else:
            threading.Thread(target=self._run_pipeline_ffmpeg, daemon=True).start()

    def _run_pipeline(self):
        """Run GStreamer pipeline with auto-restart on failure"""
        while self.running:
            try:
                self.pipeline = self._build_pipeline()
                self.pipeline.set_state(Gst.State.PLAYING)
                
                bus = self.pipeline.get_bus()
                
                while self.running:
                    msg = bus.timed_pop_filtered(
                        1000000,  # 1 second timeout
                        Gst.MessageType.ERROR | Gst.MessageType.EOS
                    )
                    
                    if msg:
                        if msg.type == Gst.MessageType.ERROR:
                            err, debug = msg.parse_error()
                            print(f"[{self.stream_id}] Pipeline error: {err}")
                            print(f"[{self.stream_id}] Debug: {debug}")
                            break
                        elif msg.type == Gst.MessageType.EOS:
                            print(f"[{self.stream_id}] End of stream")
                            break
                            
                # Cleanup
                if self.pipeline:
                    self.pipeline.set_state(Gst.State.NULL)
                    
            except Exception as e:
                print(f"[{self.stream_id}] Pipeline failed: {e}")
                
            if self.running:
                print(f"[{self.stream_id}] Restarting pipeline in 5 seconds...")
                time.sleep(5)

    def _run_pipeline_ffmpeg(self):
        """Run ffmpeg as a subprocess and restart on failure"""
        while self.running:
            try:
                cmd = self._build_ffmpeg_command()
                # Use shlex.split for safety, but keep quoted parts intact
                args = shlex.split(cmd)
                proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # Monitor process
                while self.running:
                    ret = proc.poll()
                    if ret is not None:
                        # Process exited
                        try:
                            out, err = proc.communicate(timeout=1)
                        except Exception:
                            out, err = (b"", b"")
                        print(f"[{self.stream_id}] ffmpeg exited with {ret}")
                        if err:
                            try:
                                print(err.decode('utf-8', errors='ignore'))
                            except Exception:
                                pass
                        break
                    time.sleep(1)

                # Ensure process is terminated
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except Exception:
                        proc.kill()

            except Exception as e:
                print(f"[{self.stream_id}] FFmpeg pipeline failed: {e}")

            if self.running:
                print(f"[{self.stream_id}] Restarting ffmpeg pipeline in 5 seconds...")
                time.sleep(5)

    def _restart_pipeline(self):
        """Restart pipeline with new settings"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            time.sleep(0.5)
        self._start_pipeline()

    def _log_event(self, status, fps):
        """Log motion event for web UI"""
        try:
            from datetime import datetime
            import json
            
            event_file = Path('logs') / f"events_{self.stream_id}.json"
            
            # Load existing events
            events = []
            if event_file.exists():
                try:
                    with open(event_file, 'r') as f:
                        events = json.load(f)
                except:
                    events = []
            
            # Add new event
            events.append({
                'timestamp': datetime.now().isoformat(),
                'status': status,
                'fps': fps
            })
            
            # Keep only last 100 events
            events = events[-100:]
            
            # Save
            with open(event_file, 'w') as f:
                json.dump(events, f, indent=2)
                
        except Exception as e:
            print(f"[{self.stream_id}] Event logging error: {e}")

    def update_config(self, config):
        """Update configuration and restart"""
        self.config = config
        self.detector.update_settings(
            sensitivity=config.get('motion_sensitivity'),
            min_area=config.get('motion_min_area'),
            zones=config.get('motion_zones'),
            cooldown=config.get('motion_cooldown')
        )
        self._restart_pipeline()

    def stop(self):
        """Stop streamer gracefully"""
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        self._instances.remove(self)

    @classmethod
    def set_low_quality(cls, value):
        """Set low quality mode for all streams"""
        with cls._lock:
            cls._low_quality = value
            for inst in cls._instances:
                inst._restart_pipeline()

    @classmethod
    def restart_all(cls):
        """Restart all active streamers"""
        with cls._lock:
            for inst in cls._instances:
                inst._restart_pipeline()