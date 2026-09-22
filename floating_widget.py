"""
floating_widget.py
Always-on-Top Floating Orb Voice Controller & Live Voice Selector.
Stays pinned on top of your screen across all windows (draggable, compact mini pill by default,
with 1-click expand for full widget view, live voice dropdown, mic toggle, and stop).
"""

import os
import sys
import json
import time
import webbrowser
import tkinter as tk
from tkinter import ttk
import ctypes
from ctypes import wintypes

try:
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")

VOICE_CHOICES = [
    ("en-US-BrianMultilingualNeural", "🇺🇸 Brian (Smooth Studio Male)"),
    ("en-IE-EmilyNeural", "🇮🇪 Emily (Warm Irish Female)"),
    ("en-GB-RyanNeural", "🇬🇧 Ryan (Friendly British Male)"),
    ("en-US-AvaMultilingualNeural", "🇺🇸 Ava (Conversational Female)"),
    ("en-IE-ConnorNeural", "🇮🇪 Connor (Relaxed Irish Male)"),
    ("en-AU-NatashaNeural", "🇦🇺 Natasha (Warm Australian Female)"),
    ("en-GB-SoniaNeural", "🇬🇧 Sonia (Clear British Female)"),
    ("en-CA-LiamNeural", "🇨🇦 Liam (Smooth Canadian Male)")
]

VOICE_MAP = {id_: label for id_, label in VOICE_CHOICES}
LABEL_MAP = {label: id_ for id_, label in VOICE_CHOICES}


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-US-BrianMultilingualNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "enabled": True,
        "handsfree_enabled": True,
        "auto_send": True,
        "energy_threshold": 30.0,
        "silence_timeout": 5.0,
        "stop_requested": False
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                default.update(json.load(f))
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


class FloatingOrbWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("Orb Floating Controller")
        self.root.attributes("-topmost", True)  # Initial Tkinter topmost
        self.root.overrideredirect(True)        # Sleek borderless window
        self.root.configure(bg="#070a13")

        # Initial compact placement near top-right of screen (below tab bars)
        screen_w = self.root.winfo_screenwidth()
        x = max(10, screen_w - 410)
        y = 80
        self.compact_geo = f"390x46+{x}+{y}"
        self.expanded_geo = f"390x210+{x}+{y}"
        self.is_expanded = False

        self.root.geometry(self.compact_geo)

        # Force initial window creation so we can grab the HWND
        self.root.update()
        self.hwnd = None
        if HAS_WIN32:
            try:
                self.hwnd = int(self.root.wm_frame(), 16)
                # Set WS_EX_TOPMOST (0x08) and WS_EX_TOOLWINDOW (0x80)
                cur_style = user32.GetWindowLongPtrW(self.hwnd, -20)
                user32.SetWindowLongPtrW(self.hwnd, -20, cur_style | 0x00000008 | 0x00000080)
                user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
            except Exception:
                self.hwnd = None

        # Ensure window stays pinned even when user clicks into another app
        self.root.bind("<FocusOut>", lambda e: self.root.after(10, self.enforce_topmost))

        # Dragging coordinates
        self._offset_x = 0
        self._offset_y = 0

        self.settings = load_settings()
        self.last_speech_text = ""

        self.build_ui()
        self.poll_live_state()

    def build_ui(self):
        # Outer Card with glowing blue accent border
        self.card = tk.Frame(self.root, bg="#0f172a", highlightbackground="#3b82f6", highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=0, pady=0)

        # ----------------------------------------------------
        # COMPACT TOP BAR (Always visible in mini pill mode)
        # ----------------------------------------------------
        self.top_bar = tk.Frame(self.card, bg="#0f172a", height=44)
        self.top_bar.pack(fill="x", padx=6, pady=4)
        self.top_bar.bind("<ButtonPress-1>", self.start_drag)
        self.top_bar.bind("<B1-Motion>", self.do_drag)

        # 1. Glowing Orb Button (Click to toggle mic or stop speech)
        self.btn_orb = tk.Button(
            self.top_bar,
            text="🎙️",
            font=("Segoe UI", 11, "bold"),
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            relief="flat",
            width=3,
            cursor="hand2",
            command=self.on_orb_click
        )
        self.btn_orb.pack(side="left", padx=(2, 6), pady=2)

        # 2. Status Label (Mini)
        self.lbl_status = tk.Label(
            self.top_bar,
            text="Listening",
            font=("Segoe UI", 9, "bold"),
            fg="#34d399",
            bg="#0f172a",
            cursor="fleur"
        )
        self.lbl_status.pack(side="left", padx=(0, 6))
        self.lbl_status.bind("<ButtonPress-1>", self.start_drag)
        self.lbl_status.bind("<B1-Motion>", self.do_drag)

        # 3. Live Voice Dropdown (Combobox)
        self.voice_var = tk.StringVar()
        current_voice_id = self.settings.get("voice", "en-US-BrianMultilingualNeural")
        self.voice_var.set(VOICE_MAP.get(current_voice_id, "🇺🇸 Brian (Smooth Studio Male)"))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Orb.TCombobox",
            fieldbackground="#1e293b",
            background="#1e293b",
            foreground="#f8fafc",
            darkcolor="#1e293b",
            lightcolor="#3b82f6",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            padding=3
        )

        self.combo_voice = ttk.Combobox(
            self.top_bar,
            textvariable=self.voice_var,
            values=[label for _, label in VOICE_CHOICES],
            state="readonly",
            style="Orb.TCombobox",
            width=20
        )
        self.combo_voice.pack(side="left", fill="x", expand=True, padx=(2, 6))
        self.combo_voice.bind("<<ComboboxSelected>>", self.on_voice_selected)

        # 4. Enlarge / Collapse Button (⛶)
        self.btn_expand = tk.Button(
            self.top_bar,
            text="⛶",
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            width=2,
            cursor="hand2",
            command=self.toggle_enlarge
        )
        self.btn_expand.pack(side="left", padx=(0, 3))

        # 5. Open Web Studio Button (🌐)
        self.btn_web = tk.Button(
            self.top_bar,
            text="🌐",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#60a5fa",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief="flat",
            width=2,
            cursor="hand2",
            command=self.open_web_studio
        )
        self.btn_web.pack(side="left", padx=(0, 3))

        # 6. Close Button (✕)
        self.btn_close = tk.Button(
            self.top_bar,
            text="✕",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#ef4444",
            activeforeground="#ffffff",
            relief="flat",
            width=2,
            cursor="hand2",
            command=self.root.destroy
        )
        self.btn_close.pack(side="left", padx=(0, 2))

        # ----------------------------------------------------
        # ENLARGED WIDGET BODY (Shown only when enlarged)
        # ----------------------------------------------------
        self.expanded_body = tk.Frame(self.card, bg="#0f172a", padx=10, pady=6)

        # Live Transcript Box
        self.lbl_transcript = tk.Label(
            self.expanded_body,
            text="Waiting for voice... Walk around and speak freely.",
            font=("Segoe UI", 8, "italic"),
            fg="#94a3b8",
            bg="#1e293b",
            wraplength=360,
            justify="left",
            padx=8,
            pady=6,
            relief="flat"
        )
        self.lbl_transcript.pack(fill="x", pady=(0, 8))

        # Speed Slider Row
        self.speed_frame = tk.Frame(self.expanded_body, bg="#0f172a")
        self.speed_frame.pack(fill="x", pady=(0, 6))

        tk.Label(self.speed_frame, text="Speech Speed:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#0f172a").pack(side="left")
        self.lbl_speed_val = tk.Label(self.speed_frame, text="1.00x", font=("Segoe UI", 8), fg="#38bdf8", bg="#0f172a").pack(side="right")

        self.slider_speed = tk.Scale(
            self.expanded_body,
            from_=-20,
            to=40,
            orient="horizontal",
            showvalue=0,
            bg="#1e293b",
            fg="#38bdf8",
            troughcolor="#0f172a",
            highlightthickness=0,
            command=self.on_speed_changed
        )
        cur_rate = int(str(self.settings.get("rate", "0")).replace("%", "").replace("+", "")) if self.settings.get("rate") else 0
        self.slider_speed.set(cur_rate)
        self.slider_speed.pack(fill="x", pady=(0, 8))

        # Action Buttons Row
        self.btn_row = tk.Frame(self.expanded_body, bg="#0f172a")
        self.btn_row.pack(fill="x")

        self.btn_full_studio = tk.Button(
            self.btn_row,
            text="Open Full Two-Way Studio",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            command=self.open_web_studio,
            cursor="hand2"
        )
        self.btn_full_studio.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_stop_speech = tk.Button(
            self.btn_row,
            text="🛑 Stop AI Speech",
            font=("Segoe UI", 8, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            relief="flat",
            command=self.stop_speech,
            cursor="hand2"
        )
        self.btn_stop_speech.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def start_drag(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_pointerx() - self._offset_x
        y = self.root.winfo_pointery() - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    def toggle_enlarge(self):
        curr_x = self.root.winfo_x()
        curr_y = self.root.winfo_y()
        if self.is_expanded:
            self.expanded_body.pack_forget()
            self.root.geometry(f"390x46+{curr_x}+{curr_y}")
            self.btn_expand.config(text="⛶", bg="#1e293b", fg="#94a3b8")
            self.is_expanded = False
        else:
            self.expanded_body.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            self.root.geometry(f"390x210+{curr_x}+{curr_y}")
            self.btn_expand.config(text="▲", bg="#3b82f6", fg="#ffffff")
            self.is_expanded = True
        self.enforce_topmost()

    def on_orb_click(self):
        state = load_live_state()
        if state.get("is_speaking", False):
            self.stop_speech()
            return
        
        # Toggle hands-free listening
        current = self.settings.get("handsfree_enabled", True)
        self.settings["handsfree_enabled"] = not current
        save_settings(self.settings)
        self.update_orb_visuals()

    def on_voice_selected(self, event=None):
        label = self.voice_var.get()
        voice_id = LABEL_MAP.get(label, "en-US-BrianMultilingualNeural")
        self.settings["voice"] = voice_id
        save_settings(self.settings)
        print(f"[WIDGET] Live Orb voice switched to: {label} ({voice_id})", flush=True)

    def on_speed_changed(self, val):
        v = int(float(val))
        rate_str = f"+{v}%" if v >= 0 else f"{v}%"
        mult = (100 + v) / 100.0
        self.lbl_speed_val.config(text=f"{mult:.2f}x")
        self.settings["rate"] = rate_str
        save_settings(self.settings)

    def stop_speech(self):
        state = load_live_state()
        if state.get("is_speaking", False):
            state["stop_requested"] = True
            state["is_speaking"] = False
            state["timestamp"] = time.time()
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(state, f)
            except Exception:
                pass
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass

    def open_web_studio(self):
        webbrowser.open("http://localhost:8766")

    def enforce_topmost(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            if self.hwnd and HAS_WIN32:
                # HWND_TOPMOST (-1) with SWP_NOACTIVATE (0x0010) keeps window visibly on top without stealing user focus
                user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        except Exception:
            pass

    def update_orb_visuals(self):
        state = load_live_state()
        is_speaking = state.get("is_speaking", False)
        handsfree = self.settings.get("handsfree_enabled", True)

        if is_speaking:
            self.btn_orb.config(bg="#a855f7", activebackground="#9333ea", text="🔊")
            self.lbl_status.config(text="Speaking", fg="#c084fc")
            curr = state.get("current_text", "")
            if curr and self.is_expanded:
                self.lbl_transcript.config(text=f'AI: "{curr[:110]}..."', fg="#c084fc")
        elif not handsfree:
            self.btn_orb.config(bg="#334155", activebackground="#1e293b", text="👂")
            self.lbl_status.config(text="Paused", fg="#94a3b8")
            if self.is_expanded:
                self.lbl_transcript.config(text="Microphone is paused. Tap ear to listen.", fg="#94a3b8")
        else:
            self.btn_orb.config(bg="#10b981", activebackground="#059669", text="👂")
            self.lbl_status.config(text="Listening", fg="#34d399")

    def poll_live_state(self):
        self.enforce_topmost()
        self.update_orb_visuals()
        self.root.after(250, self.poll_live_state)


def main():
    root = tk.Tk()
    app = FloatingOrbWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
