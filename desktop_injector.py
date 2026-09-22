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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

VK_MENU = 0x12
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


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
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h_proc = k32.OpenProcess(0x1000, False, pid.value)
        if h_proc:
            try:
                exe_buff = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h_proc, 0, exe_buff, ctypes.byref(size)):
                    exe_name = exe_buff.value.lower()
                    if "antigravity.exe" in exe_name:
                        rect = RECT()
                        u32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        is_iconic = bool(u32.IsIconic(hwnd))
                        if is_iconic or (w > 250 and h > 250):
                            length = u32.GetWindowTextLengthW(hwnd)
                            title = ""
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                u32.GetWindowTextW(hwnd, buff, length + 1)
                                title = buff.value
                            found_hwnds.append((hwnd, title, rect, is_iconic))
            finally:
                k32.CloseHandle(h_proc)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u32.EnumWindows(EnumWindowsProc(enum_cb), 0)

    if found_hwnds:
        fg = u32.GetForegroundWindow()
        for h, t, r, ico in found_hwnds:
            if h == fg:
                return h, r
        return found_hwnds[0][0], found_hwnds[0][2]
    return None, None


def type_text_into_antigravity(text):
    if not text or not text.strip():
        return False

    clean_text = text.strip()
    try:
        pyperclip.copy(clean_text)
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Clipboard copy error: {e}", flush=True)

    attach_default_desktop()
    hwnd, rect = find_antigravity_hwnd()

    if not hwnd or not rect:
        print(f"[DESKTOP-INJECTOR] [WARN] Antigravity window NOT FOUND — skipping injection to prevent typing into active window", flush=True)
        return False

    try:
        # 1. Restore window if minimized
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.12)

        u32.GetWindowRect(hwnd, ctypes.byref(rect))
        fg_hwnd = u32.GetForegroundWindow()

        # 2. Bring to foreground if not already foreground
        if fg_hwnd != hwnd:
            fg_thread = u32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
            target_thread = u32.GetWindowThreadProcessId(hwnd, None)
            my_thread = k32.GetCurrentThreadId()

            if fg_thread and fg_thread != target_thread:
                u32.AttachThreadInput(fg_thread, target_thread, True)
            if my_thread != target_thread:
                u32.AttachThreadInput(my_thread, target_thread, True)

            # Alt key press resets Windows foreground lock timer
            u32.keybd_event(VK_MENU, 0, 0, 0)
            u32.SetForegroundWindow(hwnd)
            u32.BringWindowToTop(hwnd)
            u32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            if fg_thread and fg_thread != target_thread:
                u32.AttachThreadInput(fg_thread, target_thread, False)
            if my_thread != target_thread:
                u32.AttachThreadInput(my_thread, target_thread, False)

            time.sleep(0.08)

        print(f"[DESKTOP-INJECTOR] [OK] Antigravity active chat targeted (hwnd={hwnd})", flush=True)
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Focus error: {e}", flush=True)

    time.sleep(0.08)

    # 3. Paste (Ctrl + V)
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
        print(f"[DESKTOP-INJECTOR] Keystroke injection done: \"{clean_text[:60]}\"", flush=True)
        return True
    except Exception as e:
        print(f"[DESKTOP-INJECTOR] Keystroke injection error: {e}", flush=True)
        return False


if __name__ == "__main__":
    test_msg = sys.argv[1] if len(sys.argv) > 1 else "Test voice relay"
    print("Testing desktop injector...")
    success = type_text_into_antigravity(test_msg)
    print("Result:", success)
