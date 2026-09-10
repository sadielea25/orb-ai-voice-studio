"""
desktop_injector.py
Cross-Desktop Window Focus & Keystroke Relay for Antigravity.
Allows background listener daemons on Windows to reliably focus Antigravity IDE on the Default desktop,
paste transcribed voice text, and submit it automatically.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
import pyperclip

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9


def attach_default_desktop():
    try:
        h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            u32.SetThreadDesktop(h_desk)
            return True
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Desktop attach warning: {e}", flush=True)
    return False


def find_antigravity_hwnd():
    attach_default_desktop()
    found_hwnds = []

    def enum_cb(hwnd, lparam):
        if u32.IsWindowVisible(hwnd):
            length = u32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                u32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                # Match Antigravity window titles
                keywords = ["submitting aa02", "dormant a", "coremarketgoods", "antigravity"]
                if any(k in title.lower() for k in keywords):
                    found_hwnds.append((hwnd, title))
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u32.EnumWindows(EnumWindowsProc(enum_cb), 0)

    if found_hwnds:
        return found_hwnds[0][0]
    return None


def type_text_into_antigravity(text):
    if not text or not text.strip():
        return False

    clean_text = text.strip()
    try:
        pyperclip.copy(clean_text)
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Clipboard copy error: {e}", flush=True)

    attach_default_desktop()
    hwnd = find_antigravity_hwnd()

    if hwnd:
        try:
            # Restore if minimized & bring to front
            u32.ShowWindow(hwnd, SW_RESTORE)
            cur_thread = k32.GetCurrentThreadId()
            target_thread = u32.GetWindowThreadProcessId(hwnd, None)
            
            if cur_thread != target_thread:
                u32.AttachThreadInput(cur_thread, target_thread, True)
                u32.SetForegroundWindow(hwnd)
                u32.SetFocus(hwnd)
                u32.AttachThreadInput(cur_thread, target_thread, False)
            else:
                u32.SetForegroundWindow(hwnd)
                u32.SetFocus(hwnd)
        except Exception as e:
            print(f"[DESKTOP-INJECTOR] Focus error: {e}", flush=True)

    time.sleep(0.08)

    # Paste (Ctrl + V)
    try:
        u32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        u32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.03)
        u32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)

        # Enter
        u32.keybd_event(VK_RETURN, 0, 0, 0)
        time.sleep(0.03)
        u32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
        print(f"[DESKTOP-INJECTOR] Successfully relayed speech to Antigravity chat: \"{clean_text}\"", flush=True)
        return True
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Keystroke injection error: {e}", flush=True)
        return False


if __name__ == "__main__":
    test_msg = sys.argv[1] if len(sys.argv) > 1 else "Test voice relay"
    print("Testing desktop injector...")
    success = type_text_into_antigravity(test_msg)
    print("Result:", success)
