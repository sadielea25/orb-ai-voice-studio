"""
watchdog_loop.py
Provides visual verification for every action taken by the desktop agent.
"""

import time
from typing import Callable, Any
from vision_engine import VisionEngine
from mouse_controller import MouseController


class WatchdogLoop:
    def __init__(self):
        self.vision = VisionEngine()
        self.mouse = MouseController()

    def execute_with_verification(
        self,
        action_name: str,
        action_fn: Callable[[], Any],
        verify_fn: Callable[[], bool],
        max_retries: int = 3,
        delay_between_retries: float = 1.0
    ) -> bool:
        """
        Executes an action, captures before & after screenshots, and checks if verification passes.
        """
        print(f"\n[Watchdog] Starting action: {action_name}")
        self.vision.capture_screen("before_action.png")

        for attempt in range(1, max_retries + 1):
            print(f"[Watchdog] Executing attempt {attempt}/{max_retries}...")
            try:
                action_fn()
                time.sleep(delay_between_retries)

                # Capture verification frame
                self.vision.capture_screen("after_action.png")

                # Run verification check
                if verify_fn():
                    print(f"[Watchdog] ✔ Action '{action_name}' succeeded and verified!")
                    return True
                else:
                    print(f"[Watchdog] ⚠ Verification check failed on attempt {attempt}.")
            except Exception as e:
                print(f"[Watchdog] Error during execution: {e}")

            time.sleep(delay_between_retries)

        print(f"[Watchdog] ✖ Action '{action_name}' failed after {max_retries} attempts.")
        return False
