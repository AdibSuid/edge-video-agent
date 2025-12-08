# motion_detector.py
import cv2
import numpy as np
import time
from threading import Lock

class MotionDetector:
    """Lightweight CPU-only motion detector using frame differencing"""

    def __init__(self, sensitivity=25, min_area=500, zones=None, cooldown=10,
                 detection_scale=0.25, blur_kernel=5, frame_skip=2):
        """
        Initialize motion detector

        Args:
            sensitivity: Threshold for motion detection (0-255, lower = more sensitive)
            min_area: Minimum contour area in pixels to count as motion
            zones: List of detection zones as [(x, y, w, h), ...]
            cooldown: Seconds to keep high FPS after last motion detected
            detection_scale: Scale factor for downsampling (0.25 = 4x smaller, faster)
            blur_kernel: Gaussian blur kernel size (smaller = faster, 5 recommended)
            frame_skip: Process every Nth frame (2 = process every other frame)
        """
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.zones = zones or []
        self.cooldown = cooldown
        self.detection_scale = detection_scale
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1  # Must be odd
        self.frame_skip = max(1, frame_skip)
        self.frame_counter = 0
        self.prev_frame = None
        self.last_motion = 0
        self.last_motion_state = False
        self.lock = Lock()

    def detect(self, frame_bgr):
        """
        Detect motion in frame with frame skipping optimization

        Args:
            frame_bgr: OpenCV BGR format frame

        Returns:
            bool: True if motion detected or still in cooldown period
        """
        with self.lock:
            # Frame skipping: only process every Nth frame
            self.frame_counter += 1
            if self.frame_counter % self.frame_skip != 0:
                # Return last known state if skipping frame
                return self.last_motion_state

            # Calculate scaled dimensions based on detection_scale
            h, w = frame_bgr.shape[:2]
            scaled_w = int(w * self.detection_scale)
            scaled_h = int(h * self.detection_scale)

            # Downsample for faster processing
            frame_bgr = cv2.resize(frame_bgr, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

            # Convert to grayscale and blur to reduce noise (optimized kernel size)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)

            # Initialize previous frame on first run
            if self.prev_frame is None:
                self.prev_frame = gray
                self.last_motion_state = False
                return False

            # Compute absolute difference between frames
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, self.sensitivity, 255, cv2.THRESH_BINARY)[1]

            # Dilate to fill in holes
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Apply zones if configured
            if self.zones:
                mask = np.zeros_like(thresh)
                for zone in self.zones:
                    if len(zone) == 4:
                        # Convert to integers to ensure valid slice indices
                        x, y, w, h = int(zone[0]), int(zone[1]), int(zone[2]), int(zone[3])
                        # Scale zone coordinates
                        x = int(x * self.detection_scale)
                        y = int(y * self.detection_scale)
                        w = int(w * self.detection_scale)
                        h = int(h * self.detection_scale)
                        # Ensure coordinates are within bounds
                        x = max(0, min(x, thresh.shape[1]))
                        y = max(0, min(y, thresh.shape[0]))
                        w = max(0, min(w, thresh.shape[1] - x))
                        h = max(0, min(h, thresh.shape[0] - y))
                        mask[y:y+h, x:x+w] = 255
                thresh = cv2.bitwise_and(thresh, thresh, mask=mask)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check if any contour is large enough (scale min_area accordingly)
            scaled_min_area = self.min_area * (self.detection_scale ** 2)
            motion = any(cv2.contourArea(c) > scaled_min_area for c in contours)

            if motion:
                self.last_motion = time.time()

            self.prev_frame = gray

            # Calculate motion state (motion detected or still in cooldown)
            self.last_motion_state = motion or (time.time() - self.last_motion < self.cooldown)
            return self.last_motion_state

    def update_settings(self, sensitivity=None, min_area=None, zones=None, cooldown=None,
                        detection_scale=None, blur_kernel=None, frame_skip=None):
        """Update detector settings on the fly"""
        with self.lock:
            if sensitivity is not None:
                self.sensitivity = sensitivity
            if min_area is not None:
                self.min_area = min_area
            if zones is not None:
                self.zones = zones
            if cooldown is not None:
                self.cooldown = cooldown
            if detection_scale is not None:
                self.detection_scale = detection_scale
            if blur_kernel is not None:
                self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
            if frame_skip is not None:
                self.frame_skip = max(1, frame_skip)