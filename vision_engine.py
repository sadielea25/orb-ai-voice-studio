"""
vision_engine.py
Captures desktop screenshots, tracks active windows, and inspects visual screen state.
"""

import os
import time
from typing import Tuple, Optional
from PIL import Image, ImageGrab
import pyautogui


class VisionEngine:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.dirname(os.path.abspath(__file__))
        os.makedirs(self.output_dir, exist_ok=True)

    def capture_screen(self, filename: str = "current_screen.png") -> str:
        """Captures a screenshot of the entire primary display and saves it."""
        filepath = os.path.join(self.output_dir, filename)
        screenshot = ImageGrab.grab()
        screenshot.save(filepath)
        return filepath

    def capture_region(self, bbox: Tuple[int, int, int, int], filename: str = "region.png") -> str:
        """Captures a specific bounding box (left, top, right, bottom)."""
        filepath = os.path.join(self.output_dir, filename)
        screenshot = ImageGrab.grab(bbox=bbox)
        screenshot.save(filepath)
        return filepath

    def find_image_on_screen(self, template_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """Locates a template image on screen and returns its center coordinates (X, Y)."""
        try:
            location = pyautogui.locateCenterOnScreen(template_path, confidence=confidence)
            return location
        except Exception:
            return None

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns (width, height) of primary monitor."""
        return pyautogui.size()
