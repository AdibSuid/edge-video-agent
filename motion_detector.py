# motion_detector.py
import cv2
import numpy as np
import time
from threading import Lock

class MotionDetector:
    """CPU motion detector using MOG2 background subtraction with noise filtering"""

    def __init__(self, sensitivity=25, min_area=500, zones=None, cooldown=10,
                 detection_scale=0.25, blur_kernel=5, frame_skip=2):
        """
        Initialize motion detector with MOG2 background subtraction

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
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1  # Must be odd
        self.frame_skip = max(1, frame_skip)
        self.frame_counter = 0
        self.last_motion = 0
        self.last_motion_state = False
        self.lock = Lock()

        # Initialize MOG2 background subtractor
        self.subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,              # Longer history for better background learning
            varThreshold=self.var_threshold,  # Variance threshold for foreground
            detectShadows=True        # Enable shadow detection
        )

    def detect(self, frame_bgr):
        """
        Detect motion in frame using MOG2 background subtraction with noise filtering

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

            # Convert to grayscale and apply Gaussian blur to reduce noise
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
                        # Convert to integers to ensure valid slice indices
                        x, y, w, h = int(zone[0]), int(zone[1]), int(zone[2]), int(zone[3])
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

            # Find contours in the foreground mask
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check if any contour is large enough (scale min_area accordingly)
            scaled_min_area = self.min_area * (self.detection_scale ** 2)
            motion = any(cv2.contourArea(c) > scaled_min_area for c in contours)

            if motion:
                self.last_motion = time.time()

            # Calculate motion state (motion detected or still in cooldown)
            self.last_motion_state = motion or (time.time() - self.last_motion < self.cooldown)
            return self.last_motion_state

    def update_settings(self, sensitivity=None, min_area=None, zones=None, cooldown=None,
                        detection_scale=None, blur_kernel=None, frame_skip=None):
        """Update detector settings"""
        with self.lock:
            if sensitivity is not None:
                # Update KNN dist2Threshold: higher sensitivity = lower threshold
                self.dist_threshold = max(100, 800 - sensitivity * 3)
                # Reinitialize subtractor with new threshold
                self.subtractor = cv2.createBackgroundSubtractorKNN(
                    history=100,
                    dist2Threshold=self.dist_threshold,
                    detectShadows=False
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
                self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
            if frame_skip is not None:
                self.frame_skip = max(1, frame_skip)
    
    def get_zones_normalized(self):
        """
        Get detection zones in normalized format (0-1 range) for UI display
        Returns: List of zones as [{"x": 0-1, "y": 0-1, "w": 0-1, "h": 0-1}, ...]
        """
        with self.lock:
            # Assuming zones are stored in pixel coordinates
            # For now, just return the zones as-is (will be normalized by UI)
            return [{"x": z[0], "y": z[1], "w": z[2], "h": z[3]} for z in self.zones if len(z) == 4]
    
    def set_zones_normalized(self, normalized_zones, frame_width, frame_height):
        """
        Set detection zones from normalized coordinates (0-1 range)
        Args:
            normalized_zones: List of {"x": 0-1, "y": 0-1, "w": 0-1, "h": 0-1}
            frame_width: Video frame width in pixels
            frame_height: Video frame height in pixels
        """
        with self.lock:
            self.zones = []
            for zone in normalized_zones:
                x = int(zone['x'] * frame_width)
                y = int(zone['y'] * frame_height)
                w = int(zone['w'] * frame_width)
                h = int(zone['h'] * frame_height)
                self.zones.append([x, y, w, h])