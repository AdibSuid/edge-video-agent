"""
Patch for streamer.py to support both JetPack 4 and JetPack 5
This shows the key changes needed to support TX2 NX (JP4) and Orin (JP5)

Apply these changes to your streamer.py:
1. Add jetpack_utils import at the top
2. Detect hardware config in __init__
3. Update GStreamer pipeline for hardware decode
4. Update FFmpeg encoder selection
"""

# ============================================================================
# CHANGE 1: Add import at the top of streamer.py (after line 20)
# ============================================================================

# Add this import after the existing imports:
from jetpack_utils import get_hardware_config, check_encoder_available, check_gstreamer_element


# ============================================================================
# CHANGE 2: In __init__ method (after line 76), detect hardware config
# ============================================================================

# Add this after self._instances.append(self) around line 77:

        # Detect JetPack version and hardware capabilities
        self.hw_config = get_hardware_config()
        self.logger.info(f"Detected hardware config: {self.hw_config['api_type']} "
                        f"(JetPack {self.hw_config['jetpack_major']}.{self.hw_config['jetpack_minor']})")


# ============================================================================
# CHANGE 3: Update _capture_loop_hw_decode (replace entire method around line 763)
# ============================================================================

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

        # Get hardware-specific decoder element
        decoder = self.hw_config.get('gstreamer_decoder', 'nvv4l2decoder')

        # Check if decoder is available
        if not check_gstreamer_element(decoder):
            self.logger.error(f"GStreamer element '{decoder}' not available")
            return False

        # Build GStreamer pipeline based on JetPack version
        if self.hw_config['api_type'] == 'omx':
            # JetPack 4.x (TX2, Xavier) - OpenMAX pipeline
            gst_pipeline = (
                f"rtspsrc location={self.rtsp_url} latency=0 ! "
                "rtph264depay ! h264parse ! "
                f"{decoder} ! nvvidconv ! "
                "video/x-raw,format=BGRx ! videoconvert ! "
                "video/x-raw,format=BGR ! appsink"
            )
            self.logger.info(f"Using JetPack 4 OMX pipeline: {decoder}")
        else:
            # JetPack 5.x+ (Orin) - V4L2 pipeline
            gst_pipeline = (
                f"rtspsrc location={self.rtsp_url} latency=0 ! "
                "rtph264depay ! h264parse ! "
                f"{decoder} ! nvvidconv ! "
                "video/x-raw,format=BGRx ! videoconvert ! "
                "video/x-raw,format=BGR ! appsink"
            )
            self.logger.info(f"Using JetPack 5+ V4L2 pipeline: {decoder}")

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
                self.logger.info(f"Captured {frame_count} frames (HW decode via {decoder})")

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


# ============================================================================
# CHANGE 4: Update _encode_chunk_hardware (replace encoder selection around line 213)
# ============================================================================

def _encode_chunk_hardware(self, frames, out_path, fps):
    """Encode video chunk using hardware acceleration for both JP4 and JP5."""
    try:
        import cv2
        if not frames:
            return False

        h, w = frames[0].shape[:2]

        # Ensure output directory exists
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Detect platform for encoder selection
        is_jetson = os.path.exists('/etc/nv_tegra_release') or os.path.exists('/sys/module/tegra_fuse')

        # Get hardware config
        hw_config = self.hw_config

        # Select encoder based on JetPack version and availability
        encoder = None
        encoder_opts = []

        if is_jetson:
            # Try primary encoder first
            primary_encoder = hw_config.get('ffmpeg_encoder', 'h264_nvenc')
            fallback_encoder = hw_config.get('ffmpeg_encoder_fallback', 'libx264')

            if check_encoder_available(primary_encoder):
                encoder = primary_encoder
                self.logger.info(f"Using primary encoder: {encoder}")

                if encoder == 'h264_nvenc':
                    # NVENC encoder (JP4 and JP5 if available)
                    encoder_opts = [
                        '-preset', 'fast',
                        '-b:v', '2M',
                        '-maxrate', '2M',
                        '-bufsize', '4M',
                    ]
                elif encoder == 'h264_omx':
                    # OMX encoder (JP4)
                    encoder_opts = [
                        '-b:v', '2M',
                    ]
            elif check_encoder_available(fallback_encoder) and fallback_encoder != 'libx264':
                # Try fallback hardware encoder
                encoder = fallback_encoder
                self.logger.info(f"Primary encoder not available, using fallback: {encoder}")

                if encoder == 'h264_v4l2m2m':
                    # V4L2M2M encoder
                    encoder_opts = [
                        '-num_output_buffers', '32',
                        '-num_capture_buffers', '16',
                        '-b:v', '2M',
                        '-maxrate', '2M',
                        '-bufsize', '4M',
                    ]
                elif encoder == 'h264_omx':
                    # OMX encoder
                    encoder_opts = [
                        '-b:v', '2M',
                    ]

        # If no hardware encoder found, fall back to software
        if not encoder:
            self.logger.warning("No hardware encoder available, using software encoding")
            return False

        # FFmpeg command with selected encoder
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

        self.logger.info(f"Encoding with {encoder}: {w}x{h} @ {fps}fps")
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Write frames to ffmpeg stdin
        frames_written = 0
        for frame in frames:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.write(frame.tobytes())
                    frames_written += 1
                else:
                    break
            except (BrokenPipeError, IOError):
                break

        # Close stdin and wait for encoding to complete
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.flush()
                proc.stdin.close()
        except Exception:
            pass

        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            self.logger.warning("Hardware encoding timeout")

        success = proc.returncode == 0 and out_path.exists()

        if success:
            self.logger.info(f"✓ Hardware encoding succeeded with {encoder}: {out_path.name}")
        else:
            self.logger.warning(f"✗ Hardware encoding failed with {encoder} (returncode={proc.returncode})")
            if stderr:
                error_msg = stderr.decode('utf-8', errors='ignore')[:500]
                self.logger.debug(f"FFmpeg stderr: {error_msg}")

        return success

    except Exception as e:
        self.logger.error(f"Hardware encoding error: {e}")
        return False
