"""
floating_widget.py
Always-on-Top Floating Conversational Desktop Widget
Draggable, sleek, real-time voice controller and live speech monitor.
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_settings.json")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_live_state.json")


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-GB-SoniaNeural",
        "rate": "+8%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "enabled": True,
        "handsfree_enabled": True,
        "auto_send": True,
        "energy_threshold": 350.0,
        "silence_timeout": 1.1,
        "stop_requested": False
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
                return default
        except Exception:
            pass
    return default


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


def load_live_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


class FloatingVoiceWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Voice Pill")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)  # Frameless sleek window
        self.root.geometry("360x220+80+80")
        self.root.configure(bg="#0f172a")

        # Draggable support
        self._offset_x = 0
        self._offset_y = 0

        self.settings = load_settings()
        self.expanded = True

        self.build_ui()
        self.poll_live_state()

    def build_ui(self):
        # Outer Card Container
        self.card = tk.Frame(self.root, bg="#1e293b", highlightbackground="#38bdf8", highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=2, pady=2)

        # Drag Header Bar
        self.header = tk.Frame(self.card, bg="#0f172a", cursor="fleur")
        self.header.pack(fill="x", padx=0, pady=0)
        self.header.bind("<ButtonPress-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.do_drag)

        self.lbl_title = tk.Label(self.header, text="✨ AI Voice Assistant", font=("Segoe UI", 10, "bold"), fg="#f8fafc", bg="#0f172a")
        self.lbl_title.pack(side="left", padx=10, pady=6)
        self.lbl_title.bind("<ButtonPress-1>", self.start_drag)
        self.lbl_title.bind("<B1-Motion>", self.do_drag)

        # Minimize / Close buttons
        self.btn_min = tk.Label(self.header, text="━", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#0f172a", cursor="hand2")
        self.btn_min.pack(side="right", padx=6)
        self.btn_min.bind("<Button-1>", self.toggle_expand)

        self.btn_close = tk.Label(self.header, text="✕", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#0f172a", cursor="hand2")
        self.btn_close.pack(side="right", padx=6)
        self.btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        # Main Body
        self.body = tk.Frame(self.card, bg="#1e293b", padx=12, pady=8)
        self.body.pack(fill="both", expand=True)

        # Status & Orb row
        self.status_row = tk.Frame(self.body, bg="#1e293b")
        self.status_row.pack(fill="x", pady=(0, 8))

        self.orb = tk.Label(self.status_row, text="●", font=("Segoe UI", 16, "bold"), fg="#10b981", bg="#1e293b")
        self.orb.pack(side="left", padx=(0, 6))

        self.lbl_status = tk.Label(self.status_row, text="Listening to room...", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b")
        self.lbl_status.pack(side="left")

        # Transcript Preview Bubble
        self.lbl_transcript = tk.Label(
            self.body,
            text="Ready. Speak anywhere in the room!",
            font=("Segoe UI", 9, "italic"),
            fg="#94a3b8",
            bg="#0f172a",
            wraplength=320,
            justify="left",
            padx=8,
            pady=6,
            relief="flat"
        )
        self.lbl_transcript.pack(fill="x", pady=(0, 10))

        # Controls Grid
        self.ctrl_frame = tk.Frame(self.body, bg="#1e293b")
        self.ctrl_frame.pack(fill="x")

        # Mode Toggle Button
        self.btn_handsfree = tk.Button(
            self.ctrl_frame,
            text="🎙️ Hands-Free: ON",
            font=("Segoe UI", 9, "bold"),
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            relief="flat",
            command=self.toggle_handsfree,
            cursor="hand2"
        )
        self.btn_handsfree.pack(side="left", expand=True, fill="x", padx=(0, 4))

        # Auto-send button
        self.btn_autosend = tk.Button(
            self.ctrl_frame,
            text="🚀 Auto-Send: ON",
            font=("Segoe UI", 9, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief="flat",
            command=self.toggle_autosend,
            cursor="hand2"
        )
        self.btn_autosend.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Stop Speech Button
        self.btn_stop = tk.Button(
            self.body,
            text="⏹️ Stop AI Speech",
            font=("Segoe UI", 9, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            relief="flat",
            command=self.stop_speech,
            cursor="hand2"
        )
        self.btn_stop.pack(fill="x", pady=(8, 0))

    def start_drag(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_pointerx() - self._offset_x
        y = self.root.winfo_pointery() - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    def toggle_expand(self, event=None):
        if self.expanded:
            self.body.pack_forget()
            self.root.geometry("220x36")
            self.btn_min.config(text="□")
            self.expanded = False
        else:
            self.body.pack(fill="both", expand=True, padx=12, pady=8)
            self.root.geometry("360x220")
            self.btn_min.config(text="━")
            self.expanded = True

    def toggle_handsfree(self):
        self.settings["handsfree_enabled"] = not self.settings.get("handsfree_enabled", True)
        save_settings(self.settings)
        if self.settings["handsfree_enabled"]:
            self.btn_handsfree.config(text="🎙️ Hands-Free: ON", bg="#10b981")
        else:
            self.btn_handsfree.config(text="🎙️ Hands-Free: OFF", bg="#64748b")

    def toggle_autosend(self):
        self.settings["auto_send"] = not self.settings.get("auto_send", True)
        save_settings(self.settings)
        if self.settings["auto_send"]:
            self.btn_autosend.config(text="🚀 Auto-Send: ON", bg="#3b82f6")
        else:
            self.btn_autosend.config(text="🚀 Auto-Send: OFF", bg="#64748b")

    def stop_speech(self):
        self.settings["stop_requested"] = True
        save_settings(self.settings)

    def poll_live_state(self):
        state = load_live_state()
        is_ai_speaking = state.get("is_speaking", False)
        stt_state = state.get("stt_state", "listening")
        last_speech = state.get("last_user_speech", "")

        if is_ai_speaking:
            self.orb.config(fg="#a855f7")  # Purple
            self.lbl_status.config(text="🔊 AI Speaking...", fg="#c084fc")
        elif stt_state == "user_speaking":
            self.orb.config(fg="#f59e0b")  # Amber
            self.lbl_status.config(text="🎙️ Hearing You...", fg="#fbbf24")
        elif stt_state == "processing":
            self.orb.config(fg="#3b82f6")  # Blue
            self.lbl_status.config(text="⏳ Transcribing...", fg="#60a5fa")
        elif not self.settings.get("handsfree_enabled", True):
            self.orb.config(fg="#64748b")  # Gray
            self.lbl_status.config(text="Mic Muted", fg="#94a3b8")
        else:
            self.orb.config(fg="#10b981")  # Green
            self.lbl_status.config(text="Listening to room...", fg="#34d399")

        if last_speech:
            self.lbl_transcript.config(text=f'You: "{last_speech}"')

        self.root.after(300, self.poll_live_state)


def main():
    root = tk.Tk()
    app = FloatingVoiceWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
