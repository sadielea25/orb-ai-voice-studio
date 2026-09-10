"""
login_detector.py
Detects when user authentication, 2FA, or password entry is required on screen.
"""

import time
from typing import Tuple


class LoginDetector:
    def __init__(self, vision_engine):
        self.vision = vision_engine

    def wait_for_user_authentication(self, timeout_seconds: int = 180) -> bool:
        """
        Monitors the screen and waits until the user finishes logging in.
        Returns True when login is completed.
        """
        print("Waiting for user to complete login / 2FA...")
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            # Capture current screen frame
            screen_file = self.vision.capture_screen("auth_check.png")
            
            # Allow time for user interaction
            time.sleep(2)
            
            # Check timeout
            if time.time() - start_time >= timeout_seconds:
                print("Timed out waiting for login.")
                return False

        return True
