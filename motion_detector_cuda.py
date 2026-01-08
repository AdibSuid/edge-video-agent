# motion_detector_cuda.py
"""
CUDA-accelerated motion detector for Jetson Orin Nano Super
Optimized for NVIDIA GPU with OpenCV CUDA support
"""
import cv2
import numpy as np
import time
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class MotionDetectorCUDA:
    """GPU-accelerated motion detector using MOG2 background subtraction with noise filtering"""

    def __init__(self, sensitivity=25, min_area=500, zones=None, cooldown=10,
                 detection_scale=0.25, blur_kernel=5, frame_skip=2):
        """
        Initialize CUDA-accelerated motion detector with MOG2 background subtraction

        Args:
            sensitivity: Motion sensitivity level (0-255, higher = more sensitive)
                        Maps to MOG2 varThreshold parameter
            min_area: Minimum contour area in pixels to count as motion
            zones: List of detection zones as [(x, y, w, h), ...]
            cooldown: Seconds to keep high FPS after last motion detected
            detection_scale: Scale factor for downsampling (0.25 = 4x smaller, faster)
            blur_kernel: Gaussian blur kernel size (smaller = faster, 5 recommended)
            frame_skip: Process every Nth frame (2 = process every other frame)
        """
        # Map sensitivity to MOG2 parameters (higher sensitivity = lower threshold)
        self.var_threshold = max(10, 200 - sensitivity * 0.75)  # 10-200 range (lower = more sensitive)
        self.min_area = min_area
        self.zones = zones or []
        self.cooldown = cooldown
        self.detection_scale = detection_scale
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        self.frame_skip = max(1, frame_skip)
        self.frame_counter = 0
        self.last_motion = 0
        self.last_motion_state = False
        self.lock = Lock()

        # Check CUDA availability
        self.cuda_available = cv2.cuda.getCudaEnabledDeviceCount() > 0
        
        if self.cuda_available:
            logger.info(f"CUDA enabled! Device count: {cv2.cuda.getCudaEnabledDeviceCount()}")
            device_info = cv2.cuda.getDevice()
            logger.info(f"Using CUDA device: {device_info}")
            
            # Pre-allocate GPU memory for common operations
            self.gpu_prev_frame = None
            self.gpu_current_frame = None
            self.gpu_gray = None
            self.gpu_diff = None
            self.gpu_thresh = None
            
            # Create CUDA filters (reusable)
            self.cuda_blur = cv2.cuda.createGaussianFilter(
                cv2.CV_8UC1, cv2.CV_8UC1, 
                (self.blur_kernel, self.blur_kernel), 0
            )
            
            # Morphological element for dilation
            self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            
            logger.info("CUDA motion detector with MOG2 initialized successfully")
        else:
            logger.warning("CUDA not available, falling back to CPU mode")

        # Initialize MOG2 background subtractor (CPU-based but optimized)
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,              # Longer history for better background learning
            varThreshold=self.var_threshold,  # Variance threshold for foreground
            detectShadows=True        # Enable shadow detection
        )

    def detect(self, frame_bgr):
        """
        Detect motion in frame using GPU acceleration

        Args:
            frame_bgr: OpenCV BGR format frame (NumPy array)

        Returns:
            bool: True if motion detected or still in cooldown period
        """
        with self.lock:
            # Frame skipping optimization
            self.frame_counter += 1
            if self.frame_counter % self.frame_skip != 0:
                return self.last_motion_state

            if self.cuda_available:
                return self._detect_cuda(frame_bgr)
            else:
                return self._detect_cpu(frame_bgr)

    def _detect_cuda(self, frame_bgr):
        """CUDA-accelerated motion detection with MOG2 background subtraction"""
        try:
            h, w = frame_bgr.shape[:2]
            scaled_w = int(w * self.detection_scale)
            scaled_h = int(h * self.detection_scale)

            # Upload frame to GPU
            gpu_frame = cv2.cuda_GpuMat()
            gpu_frame.upload(frame_bgr)

            # Resize on GPU (much faster than CPU)
            gpu_resized = cv2.cuda.resize(gpu_frame, (scaled_w, scaled_h),
                                         interpolation=cv2.INTER_LINEAR)

            gpu_gray = cv2.cuda.cvtColor(gpu_resized, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian blur on GPU
            gpu_blurred = self.cuda_blur.apply(gpu_gray)

            # Download blurred frame for MOG2 processing (CPU-based background subtraction)
            blurred_frame = gpu_blurred.download()

            # Apply MOG2 background subtraction (CPU-based but optimized)
            fg_mask = self.subtractor.apply(blurred_frame)

            # Apply morphological operations to clean up the mask and reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

            # Apply zones if configured
            if self.zones:
                mask = np.zeros_like(fg_mask)
                for zone in self.zones:
                    if len(zone) == 4:
                        x, y, w, h = [int(v) for v in zone]
                        # Scale zone coordinates
                        x = int(x * self.detection_scale)
                        y = int(y * self.detection_scale)
                        w = int(w * self.detection_scale)
                        h = int(h * self.detection_scale)
                        # Ensure coordinates are within bounds
                        x = max(0, min(x, fg_mask.shape[1]))
                        y = max(0, min(y, fg_mask.shape[0]))
                        w = max(0, min(w, fg_mask.shape[1] - x))
                        h = max(0, min(h, fg_mask.shape[0] - y))
                        mask[y:y+h, x:x+w] = 255
                fg_mask = cv2.bitwise_and(fg_mask, mask)

            # Find contours (CPU operation)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)

            # Check if any contour is large enough
            scaled_min_area = self.min_area * (self.detection_scale ** 2)
            motion = any(cv2.contourArea(c) > scaled_min_area for c in contours)

            if motion:
                self.last_motion = time.time()

            # Calculate motion state
            self.last_motion_state = motion or (time.time() - self.last_motion < self.cooldown)
            return self.last_motion_state

        except Exception as e:
            logger.error(f"CUDA detection error: {e}, falling back to CPU")
            # Fall back to CPU mode on error
            self.cuda_available = False
            return self._detect_cpu(frame_bgr)

    def _detect_cpu(self, frame_bgr):
        """Fallback CPU motion detection using MOG2 background subtraction"""
        h, w = frame_bgr.shape[:2]
        scaled_w = int(w * self.detection_scale)
        scaled_h = int(h * self.detection_scale)

        # Downsample
        frame_bgr = cv2.resize(frame_bgr, (scaled_w, scaled_h),
                              interpolation=cv2.INTER_AREA)

        # Convert to grayscale and apply Gaussian blur
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.GaussianBlur(frame_gray, (self.blur_kernel, self.blur_kernel), 0)

        # Apply MOG2 background subtraction
        fg_mask = self.subtractor.apply(frame_gray)

        # Apply morphological operations to clean up the mask and reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # Apply zones if configured
        if self.zones:
            mask = np.zeros_like(fg_mask)
            for zone in self.zones:
                if len(zone) == 4:
                    x, y, w, h = [int(v) for v in zone]
                    x = int(x * self.detection_scale)
                    y = int(y * self.detection_scale)
                    w = int(w * self.detection_scale)
                    h = int(h * self.detection_scale)
                    x = max(0, min(x, fg_mask.shape[1]))
                    y = max(0, min(y, fg_mask.shape[0]))
                    w = max(0, min(w, fg_mask.shape[1] - x))
                    h = max(0, min(h, fg_mask.shape[0] - y))
                    mask[y:y+h, x:x+w] = 255
            fg_mask = cv2.bitwise_and(fg_mask, mask)

        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL,
                                      cv2.CHAIN_APPROX_SIMPLE)

        # Check if any contour is large enough
        scaled_min_area = self.min_area * (self.detection_scale ** 2)
        motion = any(cv2.contourArea(c) > scaled_min_area for c in contours)

        if motion:
            self.last_motion = time.time()

        # Calculate motion state
        self.last_motion_state = motion or (time.time() - self.last_motion < self.cooldown)
        return self.last_motion_state

    def update_settings(self, sensitivity=None, min_area=None, zones=None,
                       cooldown=None, detection_scale=None, blur_kernel=None,
                       frame_skip=None):
        """Update detector settings on the fly"""
        with self.lock:
            if sensitivity is not None:
                # Update MOG2 varThreshold: higher sensitivity = lower threshold
                self.var_threshold = max(10, 200 - sensitivity * 0.75)
                # Reinitialize subtractor with new threshold
                self.subtractor = cv2.createBackgroundSubtractorMOG2(
                    history=500,
                    varThreshold=self.var_threshold,
                    detectShadows=True
                )
            if min_area is not None:
                self.min_area = min_area
            if zones is not None:
                self.zones = zones
            if cooldown is not None:
                self.cooldown = cooldown
            if detection_scale is not None:
                self.detection_scale = detection_scale
            if blur_kernel is not None:
                new_blur = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
                if new_blur != self.blur_kernel and self.cuda_available:
                    self.blur_kernel = new_blur
                    # Recreate CUDA blur filter
                    self.cuda_blur = cv2.cuda.createGaussianFilter(
                        cv2.CV_8UC1, cv2.CV_8UC1, 
                        (self.blur_kernel, self.blur_kernel), 0
                    )
            if frame_skip is not None:
                self.frame_skip = max(1, frame_skip)

    def get_info(self):
        """Get detector information"""
        return {
            'cuda_available': self.cuda_available,
            'cuda_device_count': cv2.cuda.getCudaEnabledDeviceCount() if self.cuda_available else 0,
            'detection_scale': self.detection_scale,
            'frame_skip': self.frame_skip,
            'mode': 'GPU' if self.cuda_available else 'CPU'
        }
