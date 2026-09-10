"""
mouse_controller.py
Provides physical mouse movement, clicks, scrolling, and keyboard typing.
"""

import time
import pyautogui
import pyperclip

# Safety settings: moving mouse to screen corner aborts
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


class MouseController:
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()

    def move_to(self, x: int, y: int, duration: float = 0.4):
        """Smoothly moves the mouse cursor to (x, y)."""
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)

    def click(self, x: int = None, y: int = None, clicks: int = 1, interval: float = 0.1):
        """Clicks at the current or specified coordinates."""
        if x is not None and y is not None:
            self.move_to(x, y)
        pyautogui.click(clicks=clicks, interval=interval)
        time.sleep(0.1)

    def double_click(self, x: int = None, y: int = None):
        """Double clicks at (x, y)."""
        self.click(x, y, clicks=2, interval=0.15)

    def right_click(self, x: int = None, y: int = None):
        """Right clicks at (x, y)."""
        if x is not None and y is not None:
            self.move_to(x, y)
        pyautogui.rightClick()

    def clear_and_type(self, text: str, x: int = None, y: int = None):
        """Clicks an input box, selects all text (Ctrl+A), deletes it, and types new text."""
        if x is not None and y is not None:
            self.click(x, y)
        else:
            pyautogui.click()
        
        # Select all and delete
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.05)
        pyautogui.press('backspace')
        time.sleep(0.05)
        
        # Type text (or paste via clipboard if contains special characters)
        if any(c in text for c in ['£', '€', '©', '\n']):
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.write(text, interval=0.03)
        time.sleep(0.1)

    def press_key(self, key_name: str, presses: int = 1):
        """Presses a keyboard key (e.g. 'tab', 'enter', 'esc', 'space')."""
        for _ in range(presses):
            pyautogui.press(key_name)
            time.sleep(0.05)

    def hotkey(self, *keys):
        """Presses a combination of keys (e.g. ('ctrl', 'c'))."""
        pyautogui.hotkey(*keys)
        time.sleep(0.1)

    def scroll(self, clicks: int):
        """Scrolls the mouse wheel up (positive) or down (negative)."""
        pyautogui.scroll(clicks)
        time.sleep(0.2)
