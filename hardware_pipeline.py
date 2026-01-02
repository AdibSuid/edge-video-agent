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
    
    def __init__(self, stream_id, rtsp_url, config):
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.config = config
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
        """Run the GStreamer pipeline process"""
        output_dir = Path('tmp/hw_chunks') / self.stream_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        bitrate = int(self.config.get('chunk_bitrate', 2000000))
        chunk_duration_ns = int(self.config.get('chunk_duration', 5)) * 1000000000  # Convert to nanoseconds
        
        # Pure GStreamer pipeline - 100% hardware, 0% CPU
        pipeline = [
            'gst-launch-1.0', '-e',
            'rtspsrc', f'location={self.rtsp_url}', 'latency=200', 'protocols=tcp',
            '!', 'queue', 'max-size-buffers=2', 'leaky=downstream',
            '!', 'rtph264depay',
            '!', 'h264parse',
            '!', 'nvv4l2decoder', 'enable-max-performance=1',  # NVDEC continuously active
            '!', 'nvvidconv',
            '!', 'video/x-raw(memory:NVMM)',
            '!', 'nvv4l2h264enc', f'bitrate={bitrate}', 'preset-level=1', 'insert-sps-pps=true',  # NVENC continuously active
            '!', 'h264parse',
            '!', 'splitmuxsink', f'location={output_dir}/{self.stream_id}_%05d.mp4', 
            f'max-size-time={chunk_duration_ns}', 'max-files=100'  # Auto-rotate, keep last 100 chunks
        ]
        
        self.logger.info(f"Starting pipeline: {' '.join(pipeline[:15])}...")
        
        while self.running:
            try:
                self.process = subprocess.Popen(
                    pipeline,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Create new process group for clean termination
                )
                
                self.logger.info("✓ NVDEC + NVENC pipeline running (continuous hardware acceleration)")
                
                # Monitor stderr for errors
                for line in self.process.stderr:
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if 'ERROR' in line_str or 'WARNING' in line_str:
                        self.logger.warning(f"GStreamer: {line_str}")
                
                # Process ended
                self.process.wait()
                
                if self.running:
                    self.logger.warning("Pipeline died, restarting in 5s...")
                    time.sleep(5)
                else:
                    break
                    
            except Exception as e:
                self.logger.error(f"Pipeline error: {e}")
                if self.running:
                    time.sleep(5)
                else:
                    break
        
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