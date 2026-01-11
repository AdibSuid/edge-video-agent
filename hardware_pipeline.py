"""
Pure GStreamer hardware pipeline manager.
Keeps NVDEC/NVENC continuously active with zero CPU involvement.
"""

import subprocess
import threading
import time
from pathlib import Path
import logging
import signal
import os
import shutil


class HardwarePipeline:
    """Manages pure GStreamer hardware pipeline for continuous NVDEC/NVENC usage"""
    
    def __init__(self, stream_id, rtsp_url, config, output_file=None):
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.config = config
        self.output_file = output_file  # Single output file for entire motion event
        self.process = None
        self.running = False
        self.logger = self._setup_logger()

        # Find gst-launch-1.0 executable
        self.gst_launch_path = shutil.which('gst-launch-1.0')
        if not self.gst_launch_path:
            # Try common Windows locations
            common_paths = [
                r'C:\Program Files\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe',
                r'C:\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe',
                r'C:\Program Files (x86)\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe'
            ]
            for path in common_paths:
                if os.path.exists(path):
                    self.gst_launch_path = path
                    break
        
        if not self.gst_launch_path:
            self.logger.error("gst-launch-1.0 not found. Hardware pipeline may not work.")
        else:
            self.logger.info(f"Found gst-launch-1.0 at: {self.gst_launch_path}")
        
    def _setup_logger(self):
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger(f'hw-pipeline-{self.stream_id}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            fh = logging.FileHandler(log_dir / f'hw_pipeline_{self.stream_id}.log')
            fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            logger.addHandler(fh)
        
        return logger
    
    def start(self):
        """Start the pure GStreamer hardware pipeline"""
        if self.running:
            self.logger.warning("Pipeline already running")
            return
        
        self.running = True
        threading.Thread(target=self._run_pipeline, daemon=True).start()
        self.logger.info("✓ Hardware pipeline started")
    
    def _run_pipeline(self):
        """Run the GStreamer pipeline process - records chunks based on chunk_duration"""
        # Save directly to tmp/chunks like old version
        output_dir = Path('tmp/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get chunk duration from config (5-15 seconds range)
        chunk_duration = int(self.config.get('chunk_duration', 5))
        chunk_duration_ns = chunk_duration * 1000000000  # Convert to nanoseconds
        
        # Generate base filename pattern for splitmuxsink
        timestamp = int(time.time())
        output_pattern = str(output_dir / f"{self.stream_id}_{timestamp}_%05d.mp4")
        
        bitrate = int(self.config.get('chunk_bitrate', 2000000))
        
        # Strategy: Force keyframes more frequently to enable precise splits
        # Use a shorter GOP (Group of Pictures) to ensure keyframes align with chunk duration
        # For 8 second chunks with 25fps: we need keyframes every 1-2 seconds max
        fps = 25  # Assume 25fps for most CCTV cameras
        
        # Set keyframe interval to half the chunk duration to ensure at least 2 keyframes per chunk
        # This allows splitmuxsink to split closer to the target time
        keyframe_interval = max(fps // 2, 15)  # Minimum 15 frames (0.6s), or half-second for better splits
        
        # Calculate approximate max bytes per chunk (as backup split trigger)
        # bitrate is in bits/sec, convert to bytes and multiply by duration
        max_bytes = int((bitrate / 8) * chunk_duration * 1.1)  # 10% buffer
        
        # FIXED CHUNK DURATION MODE: Split based on chunk_duration setting
        # Uses splitmuxsink to create fixed-duration chunks
        pipeline = [
            self.gst_launch_path or 'gst-launch-1.0', '-e',
            'uridecodebin',
            f'uri={self.rtsp_url}',
            'protocols=tcp',  # Force TCP to avoid packet loss
            'latency=200',    # Add latency buffer for reference frame recovery
            '!', 'queue',
            'max-size-buffers=10',
            'leaky=downstream',
            '!', 'nvvidconv',
            '!', 'video/x-raw(memory:NVMM),format=I420',
            '!', 'nvv4l2h264enc',
            f'bitrate={bitrate}',
            'preset-level=1',
            'insert-sps-pps=true',
            f'idrinterval={keyframe_interval}',  # Frequent keyframes for precise time-based splits
            'insert-vui=true',  # Insert VUI for better timing info
            '!', 'h264parse',
            'config-interval=1',  # Insert config (SPS/PPS) at every IDR
            '!', 'video/x-h264,stream-format=avc,alignment=au',
            '!', 'splitmuxsink',  # Split into fixed-duration chunks
            f'location={output_pattern}',
            f'max-size-time={chunk_duration_ns}',  # Primary: Split every N seconds
            f'max-size-bytes={max_bytes}',  # Secondary: Size limit as backup
            'send-keyframe-requests=true',  # Request keyframes at split points
            'muxer-factory=qtmux',
            'muxer-properties="properties,faststart=true"',
            'async-finalize=true'  # Finalize files in background
        ]
        
        self.logger.info(f"Recording chunks with {chunk_duration}s duration to: {output_pattern}")
        self.logger.info(f"Pipeline command: {' '.join(pipeline)}")
        
        # Start pipeline (no auto-reconnect, just record this one event)
        try:
            self.process = subprocess.Popen(
                pipeline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.logger.info(f"✓ NVDEC + NVENC pipeline active - recording {chunk_duration}s chunks")
            
            # Monitor stderr for errors
            for line in self.process.stderr:
                line_str = line.decode('utf-8', errors='ignore').strip()
                
                if line_str:
                    if 'ERROR' in line_str:
                        self.logger.error(f"GStreamer: {line_str}")
                    elif 'WARNING' in line_str:
                        self.logger.warning(f"GStreamer: {line_str}")
            
            # Process ended
            self.process.wait()
            self.logger.info(f"Recording complete")
                
        except Exception as e:
            self.logger.error(f"Pipeline exception: {e}")
        finally:
            self.running = False
        
        self.logger.info("Hardware pipeline stopped")
    
    def stop(self):
        """Stop the pipeline gracefully"""
        self.logger.info("Stopping hardware pipeline...")
        self.running = False

        if self.process:
            try:
                # Send SIGINT to process group (graceful shutdown)
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if needed
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
            except Exception as e:
                self.logger.error(f"Error stopping pipeline: {e}")

        self.logger.info("✓ Hardware pipeline stopped")

    def cleanup_logger(self):
        """Close all logger handlers to release file locks"""
        if self.logger:
            handlers = self.logger.handlers[:]
            for handler in handlers:
                handler.close()
                self.logger.removeHandler(handler)