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
        """Run the GStreamer pipeline process - records ONE continuous file per motion event"""
        # Save directly to tmp/chunks like old version
        output_dir = Path('tmp/chunks')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use the provided output file or generate one
        if not self.output_file:
            import uuid
            chunk_id = str(uuid.uuid4())[:8]
            self.output_file = output_dir / f"{self.stream_id}_{chunk_id}.mp4"
        else:
            self.output_file = Path(self.output_file)
        
        bitrate = int(self.config.get('chunk_bitrate', 2000000))
        
        # COMMERCIAL CCTV MODE: Record entire motion event as ONE continuous video
        # No splitmuxsink, just direct MP4 recording
        pipeline = [
            'gst-launch-1.0', '-e',
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
            'idrinterval=30',  # Regular keyframes for seekability
            '!', 'h264parse',
            '!', 'video/x-h264,stream-format=avc,alignment=au',
            '!', 'qtmux',  # Direct MP4 muxing (no splitting)
            'faststart=true',
            'fragment-duration=1000',
            '!', 'filesink',
            f'location={self.output_file}',
            'sync=false'  # Don't block on disk writes
        ]
        
        self.logger.info(f"Recording motion event to: {self.output_file}")
        self.logger.info(f"Pipeline command: {' '.join(pipeline)}")
        
        # Start pipeline (no auto-reconnect, just record this one event)
        try:
            self.process = subprocess.Popen(
                pipeline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            self.logger.info("✓ NVDEC + NVENC pipeline active - recording motion event")
            
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
            self.logger.info(f"Recording complete: {self.output_file}")
                
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