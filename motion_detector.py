# motion_detector.py
import cv2
import numpy as np
import time
from threading import Lock

class MotionDetector:
    """Lightweight CPU-only motion detector using frame differencing"""
    
    def __init__(self, sensitivity=25, min_area=500, zones=None, cooldown=10):
        """
        Initialize motion detector
        
        Args:
            sensitivity: Threshold for motion detection (0-255, lower = more sensitive)
            min_area: Minimum contour area in pixels to count as motion
            zones: List of detection zones as [(x, y, w, h), ...]
            cooldown: Seconds to keep high FPS after last motion detected
        """
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.zones = zones or []
        self.cooldown = cooldown
        self.prev_frame = None
        self.last_motion = 0
        self.lock = Lock()

    def detect(self, frame_bgr):
        """
        Detect motion in frame

        Args:
            frame_bgr: OpenCV BGR format frame

        Returns:
            bool: True if motion detected or still in cooldown period
        """
        with self.lock:
            # Downsample to 640x360 for faster processing (4x fewer pixels)
            frame_bgr = cv2.resize(frame_bgr, (640, 360), interpolation=cv2.INTER_AREA)

            # Convert to grayscale and blur to reduce noise
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # Initialize previous frame on first run
            if self.prev_frame is None:
                self.prev_frame = gray
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
                        # Ensure coordinates are within bounds
                        x = max(0, min(x, thresh.shape[1]))
                        y = max(0, min(y, thresh.shape[0]))
                        w = max(0, min(w, thresh.shape[1] - x))
                        h = max(0, min(h, thresh.shape[0] - y))
                        mask[y:y+h, x:x+w] = 255
                thresh = cv2.bitwise_and(thresh, thresh, mask=mask)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Check if any contour is large enough
            motion = any(cv2.contourArea(c) > self.min_area for c in contours)
            
            if motion:
                print(f"[MOTION] Detected motion with {len(contours)} contours, areas: {[cv2.contourArea(c) for c in contours]}")
                self.last_motion = time.time()

            self.prev_frame = gray
            
            # Return True if motion detected or still in cooldown
            in_cooldown = (time.time() - self.last_motion < self.cooldown)
            if in_cooldown:
                print(f"[MOTION] In cooldown, last motion {time.time() - self.last_motion:.1f}s ago")
            return motion or in_cooldown

    def update_settings(self, sensitivity=None, min_area=None, zones=None, cooldown=None):
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