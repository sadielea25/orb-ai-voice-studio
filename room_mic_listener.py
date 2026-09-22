"""
room_mic_listener.py
High-Sensitivity Physical Background Microphone Listener for Full Hands-Free Room Walking.
Includes 300ms pre-speech audio ring buffer, instant barge-in interruption, and auto-typing.
"""
import os, sys, time, json, collections, threading, urllib.request, pyperclip, ctypes, re
from ctypes import wintypes
import numpy as np, sounddevice as sd, speech_recognition as sr

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")

SAMPLE_RATE = 44100   # Mic native rate — must match hardware or sounddevice returns silence
STT_RATE = 16000      # Google STT native rate — we downsample before sending
CHUNK_DURATION = 0.05
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
PRE_BUFFER_COUNT = 6  # 300ms pre-trigger buffer
MIC_DEVICE = 1        # Microphone (Realtek High Definition Audio)

user32 = ctypes.windll.user32
winmm = ctypes.windll.winmm
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002


def send_windows_paste_and_enter():
    try:
        time.sleep(0.06)
        # Ctrl + V
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)
        # Enter
        user32.keybd_event(VK_RETURN, 0, 0, 0)
        time.sleep(0.04)
        user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[ROOM-MIC Key Injection Error]: {e}", flush=True)


def is_ai_speaking():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("is_speaking", False)
        except Exception:
            pass
    return False


def request_stop_ai_playback():
    try:
        sd.stop()
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"is_speaking": False, "stop_requested": True, "timestamp": time.time()}, f)
    except Exception:
        pass


def load_threshold():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return float(data.get("energy_threshold", 45.0))
        except Exception:
            pass
    return 45.0


def append_to_conversation(text):
    try:
        data = json.dumps({"text": text, "source": "room_mic"}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8766/api/speech_input",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception as e:
        print(f"[ROOM-MIC API Error]: {e}", flush=True)


def trigger_stop_speech():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        else:
            state = {}
        state["stop_requested"] = True
        state["is_speaking"] = False
        state["timestamp"] = time.time()
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass
    try:
        sd.stop()
    except Exception:
        pass


def is_headphones_active():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
                dev = s.get("device_name", "").lower()
                if any(h in dev for h in ["budi", "headphone", "headset", "earphone"]):
                    return True
        except Exception:
            pass
    return False


def clean_words(text):
    return [w for w in re.sub(r'[^a-z0-9 ]', ' ', text.lower()).split() if w]


def find_longest_common_phrase(words1, words2):
    set2_str = ' ' + ' '.join(words2) + ' '
    max_len = 0
    for i in range(len(words1)):
        for j in range(i + 4, min(len(words1) + 1, i + 35)):
            phrase = ' ' + ' '.join(words1[i:j]) + ' '
            if phrase in set2_str:
                max_len = max(max_len, j - i)
    return max_len


def is_echo_of_ai(text):
    if not text:
        return False

    user_words = clean_words(text)
    if len(user_words) < 4:
        return False

    ai_texts = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                curr = state.get("current_text", "").strip()
                if curr:
                    ai_texts.append(curr)
        except Exception:
            pass

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                for item in history[:15]:
                    txt = item.get("text", "").strip()
                    if txt:
                        ai_texts.append(txt)
        except Exception:
            pass

    for ai_t in ai_texts:
        ai_words = clean_words(ai_t)
        if not ai_words:
            continue
        max_seq = find_longest_common_phrase(user_words, ai_words)
        if max_seq >= 4:
            return True

    return False


def escape_key_listener():
    while True:
        try:
            # VK_ESCAPE is 0x1B
            if user32.GetAsyncKeyState(0x1B) & 0x8000:
                if is_ai_speaking():
                    trigger_stop_speech()
                    print("\n[ROOM-MIC] 🛑 ESC key pressed! Interrupted AI playback immediately.", flush=True)
                    time.sleep(0.35)
        except Exception:
            pass
        time.sleep(0.04)


def keep_orb_window_topmost():
    try:
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SetWindowPos.restype = wintypes.BOOL
    except Exception:
        pass

    SWP_FLAGS = 0x0001 | 0x0002 | 0x0010 | 0x0040  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW

    while True:
        try:
            h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                user32.SetThreadDesktop(h_desk)

            def enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if "orb ai" in title or "orb voice" in title:
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            w = rect.right - rect.left
                            if w < 750:
                                style = user32.GetWindowLongPtrW(hwnd, -20)
                                is_top = bool(style & 0x00000008) if style else False
                                if not is_top:
                                    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, SWP_FLAGS)
                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
        except Exception:
            pass
        time.sleep(1.0)


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"energy_threshold": 45.0, "silence_timeout": 5.0}


def strip_send_trigger(text):
    if not text:
        return text, False
    words = text.strip().split()
    if not words:
        return text, False
    send_triggers = {"go", "send", "sand", "sent", "cent", "scent", "submit", "done"}
    send_phrases = {"go now", "lets go", "let's go", "go ahead", "send it", "send that", "send now", "send message", "sand it", "please send", "send this"}
    last_one = words[-1].lower().strip(".,!?")
    last_two = " ".join(w.lower().strip(".,!?") for w in words[-2:]) if len(words) >= 2 else ""
    if last_two in send_phrases:
        remaining = " ".join(words[:-2]).strip()
        return remaining, True
    if last_one in send_triggers:
        remaining = " ".join(words[:-1]).strip()
        return remaining, True
    return text.strip(), False


class RoomMicListener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 50
        self.recognizer.dynamic_energy_threshold = False
        self.is_recording = False
        self.audio_frames = []
        self.pre_buffer = collections.deque(maxlen=PRE_BUFFER_COUNT)
        self.silence_start = None
        self.intermediate_checked = False
        self.is_transcribing = False

    def transcribe_audio_chunk(self, frames):
        try:
            raw_pcm = np.concatenate(frames)
            audio_data = sr.AudioData(raw_pcm.tobytes(), SAMPLE_RATE, 2)
            raw_text = ""
            try:
                raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            except Exception:
                try:
                    raw_text = self.recognizer.recognize_google(audio_data, language="en-US")
                except Exception:
                    raw_text = ""
            return raw_text.strip()
        except Exception:
            return ""

    def transcribe_and_send(self, frames):
        try:
            self.is_transcribing = True

            # Trim trailing silence chunks (keep only speech + 0.6s buffer)
            thresh = max(20.0, load_threshold() * 0.4)
            speech_end_idx = len(frames)
            for i in range(len(frames) - 1, -1, -1):
                chunk_rms = np.sqrt(np.mean(frames[i].astype(np.float32) ** 2))
                if chunk_rms > thresh:
                    speech_end_idx = min(len(frames), i + int(0.6 / CHUNK_DURATION))
                    break
            trimmed_frames = frames[:speech_end_idx] if speech_end_idx > int(0.3 / CHUNK_DURATION) else frames

            raw_pcm = np.concatenate(trimmed_frames)
            duration_s = len(raw_pcm) / SAMPLE_RATE
            print(f"[ROOM-MIC] Transcribing {duration_s:.1f}s of audio (peak: {np.max(np.abs(raw_pcm))})...", flush=True)

            # Use native 44.1kHz 16-bit PCM directly (lossless FLAC to Google STT)
            audio_data = sr.AudioData(raw_pcm.tobytes(), SAMPLE_RATE, 2)

            raw_text = ""
            try:
                raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            except sr.UnknownValueError:
                try:
                    raw_text = self.recognizer.recognize_google(audio_data, language="en-US")
                except Exception as e:
                    print(f"[ROOM-MIC] STT unrecognized audio: {e}", flush=True)
            except Exception as e:
                try:
                    raw_text = self.recognizer.recognize_google(audio_data, language="en-US")
                except Exception:
                    print(f"[ROOM-MIC] STT API error: {e}", flush=True)

            cleaned = raw_text.strip()
            if cleaned:
                # Echo Rejection: Check if Google STT transcribed the AI's own speaker output
                if is_echo_of_ai(cleaned):
                    print(f"\n[ROOM-MIC] 🔇 Blocked speaker acoustic echo: \"{cleaned}\"", flush=True)
                    return

                # Discard audio if it was recorded within 0.6s of AI speaking (decay echo), unless it was a vocal cut-in
                is_barge_in = getattr(self, "barge_in_active", False)
                self.barge_in_active = False
                if not is_barge_in and (time.time() - self.last_ai_speech_time < 0.6):
                    print(f"\n[ROOM-MIC] 🔇 Dropped speech chunk captured during/immediately after AI speech: \"{cleaned}\"", flush=True)
                    return

                # Contextual Accent & Common Sense Adaptation for Sadie's voice
                try:
                    import accent_adapter
                    cleaned = accent_adapter.adapt_speech_text(cleaned)
                except Exception as e:
                    pass

                # Strip trailing 'go' / 'send' trigger if spoken
                clean_text, had_send = strip_send_trigger(cleaned)
                if not clean_text and had_send:
                    return

                final_text = clean_text if clean_text else cleaned
                safe_text = final_text.encode("ascii", "ignore").decode("ascii")
                print(f"\n========================================", flush=True)
                print(f"  [YOU SAID]: \"{safe_text}\" (send_trigger={had_send})", flush=True)
                print(f"========================================\n", flush=True)

                # 1. Update clipboard and inject keystrokes into Antigravity
                try:
                    import desktop_injector
                    desktop_injector.type_text_into_antigravity(final_text)
                except Exception as e:
                    print(f"[ROOM-MIC Inject Error]: {e}", flush=True)

                # 2. Append to server stream
                append_to_conversation(final_text)

        except Exception as e:
            print(f"[ROOM-MIC STT Error]: {e}", flush=True)
        finally:
            self.is_transcribing = False

    def run(self):
        print("\n[ROOM-MIC] ========================================================", flush=True)
        print("[ROOM-MIC] Physical Background Microphone Listener Active on Windows!", flush=True)
        print("[ROOM-MIC] Auto-Typing & Auto-Send Enabled for Active Chat!", flush=True)
        print("[ROOM-MIC] Echo Cancellation & Seamless Barge-In: ENABLED", flush=True)
        print("[ROOM-MIC] Cut-in: Press ESC or click Orb on speakers; speak to interrupt on headphones", flush=True)
        print("[ROOM-MIC] ========================================================\n", flush=True)

        self.last_ai_speech_time = 0.0

        # Start ESC key cut-in listener
        threading.Thread(target=escape_key_listener, daemon=True).start()

        # Start persistent always-on-top enforcer for Orb AI window
        threading.Thread(target=keep_orb_window_topmost, daemon=True).start()

        def audio_callback(indata, frames, time_info, status):
            try:
                # Mix stereo to mono (channel 0 alone can be empty on some Realtek setups)
                audio_chunk = indata[:, 0].astype(np.int32)
                if indata.shape[1] > 1:
                    audio_chunk = ((audio_chunk + indata[:, 1].astype(np.int32)) // 2)
                audio_chunk = audio_chunk.astype(np.int16)
                rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
                threshold = load_threshold()
                ai_active = is_ai_speaking()

                # Guard 1: When AI is speaking
                if ai_active:
                    self.last_ai_speech_time = time.time()
                    
                    if is_headphones_active():
                        # On headphones, no speaker bleed into mic!
                        barge_thresh = max(threshold * 1.5, 90.0)
                    else:
                        # On laptop speakers: Maintain rolling average of speaker bleed RMS
                        if not hasattr(self, "speaker_rms_avg") or self.speaker_rms_avg is None:
                            self.speaker_rms_avg = rms
                        else:
                            self.speaker_rms_avg = 0.82 * self.speaker_rms_avg + 0.18 * rms
                        # Vocal surge over speaker baseline
                        barge_thresh = max(threshold * 2.2, self.speaker_rms_avg * 1.35, 650.0)

                    if rms > barge_thresh:
                        self.cut_in_count = getattr(self, "cut_in_count", 0) + 1
                        if self.cut_in_count >= 2:
                            self.cut_in_count = 0
                            trigger_stop_speech()
                            print(f"\n[ROOM-MIC] 🛑 Vocal cut-in detected (RMS: {rms:.1f} vs thresh {barge_thresh:.1f})! Paused AI to listen to you...", flush=True)
                            self.is_recording = True
                            self.audio_frames = list(self.pre_buffer) + [audio_chunk]
                            self.silence_start = None
                            self.intermediate_checked = False
                            self.barge_in_active = True
                            self.last_ai_speech_time = 0.0
                            return
                    else:
                        self.cut_in_count = 0

                    if not self.is_recording:
                        self.audio_frames = []
                        self.pre_buffer.append(audio_chunk)
                    return

                # Guard 2: Reverb decay guard: 0.6s after AI speech finishes, ignore decaying room acoustics (only if not recording)
                if not self.is_recording and (time.time() - self.last_ai_speech_time < 0.6):
                    self.pre_buffer.clear()
                    self.audio_frames = []
                    self.is_recording = False
                    return

                # User speech detection when AI is not speaking
                settings = load_settings()
                if not settings.get("handsfree_enabled", True):
                    self.pre_buffer.clear()
                    self.audio_frames = []
                    self.is_recording = False
                    return

                silence_timeout = float(settings.get("silence_timeout", 5.0))

                if rms > threshold:
                    self.speech_chunks_count = getattr(self, "speech_chunks_count", 0) + 1
                    if not self.is_recording:
                        if self.speech_chunks_count >= 2:
                            self.is_recording = True
                            self.audio_frames = list(self.pre_buffer) + [audio_chunk]
                            self.silence_start = None
                            self.intermediate_checked = False
                            print(f"\n[ROOM-MIC] Voice detected (RMS: {rms:.1f})! Listening...", flush=True)
                        else:
                            self.pre_buffer.append(audio_chunk)
                    else:
                        self.audio_frames.append(audio_chunk)
                        self.silence_start = None
                        self.intermediate_checked = False

                    # Max duration cut (45s max per thought to prevent infinite hanging)
                    if len(self.audio_frames) * CHUNK_DURATION >= 45.0:
                        self.is_recording = False
                        captured = list(self.audio_frames)
                        self.audio_frames = []
                        self.silence_start = None
                        self.intermediate_checked = False
                        threading.Thread(
                            target=self.transcribe_and_send,
                            args=(captured,),
                            daemon=True
                        ).start()
                else:
                    self.speech_chunks_count = 0
                    if not self.is_recording:
                        self.pre_buffer.append(audio_chunk)
                    else:
                        self.audio_frames.append(audio_chunk)
                        if self.silence_start is None:
                            self.silence_start = time.time()
                            self.intermediate_checked = False
                        else:
                            silence_dur = time.time() - self.silence_start

                            # Instant trigger: if paused for >= 0.4s and Sadie said 'Go' or 'Send', dispatch immediately!
                            if silence_dur >= 0.4 and not self.intermediate_checked and not self.is_transcribing:
                                self.intermediate_checked = True
                                current_frames = list(self.audio_frames)
                                if len(current_frames) >= int(0.5 / CHUNK_DURATION):
                                    def bg_check(frames_to_check):
                                        text = self.transcribe_audio_chunk(frames_to_check)
                                        if not text:
                                            return
                                        try:
                                            import accent_adapter
                                            text = accent_adapter.adapt_speech_text(text)
                                        except Exception:
                                            pass
                                        clean_text, had_send = strip_send_trigger(text)
                                        if had_send and clean_text:
                                            print(f"\n[ROOM-MIC] 🚀 'Go' trigger spoken! Dispatching straight away: \"{clean_text}\"", flush=True)
                                            self.is_recording = False
                                            self.audio_frames = []
                                            self.silence_start = None
                                            self.intermediate_checked = False
                                            try:
                                                import desktop_injector
                                                desktop_injector.type_text_into_antigravity(clean_text)
                                            except Exception as e:
                                                print(f"[ROOM-MIC Inject Error]: {e}", flush=True)
                                            append_to_conversation(clean_text)

                                    threading.Thread(target=bg_check, args=(current_frames,), daemon=True).start()

                            # Auto-send after 5.0s of uninterrupted silence
                            if silence_dur >= silence_timeout:
                                self.is_recording = False
                                captured = list(self.audio_frames)
                                self.audio_frames = []
                                self.silence_start = None
                                self.intermediate_checked = False
                                if len(captured) >= int(0.55 / CHUNK_DURATION):
                                    threading.Thread(
                                        target=self.transcribe_and_send,
                                        args=(captured,),
                                        daemon=True
                                    ).start()
            except Exception as e:
                pass

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=2,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            while True:
                time.sleep(0.1)


if __name__ == "__main__":
    listener = RoomMicListener()
    listener.run()


