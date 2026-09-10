"""
room_mic_listener.py
High-Sensitivity Physical Background Microphone Listener for Full Hands-Free Room Walking.
Includes 300ms pre-speech audio ring buffer, instant barge-in interruption, and auto-typing.
"""
import os, sys, time, json, collections, threading, urllib.request, pyperclip, ctypes
import numpy as np, sounddevice as sd, speech_recognition as sr

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")

SAMPLE_RATE = 44100
CHUNK_DURATION = 0.05
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
PRE_BUFFER_COUNT = 6  # 300ms pre-trigger buffer

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
        winmm.mciSendStringW("stop all", None, 0, None)
        winmm.mciSendStringW("close all", None, 0, None)
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
        data = json.dumps({"text": text, "auto_send": True}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8766/api/speech_input",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception as e:
        print(f"[ROOM-MIC API Error]: {e}", flush=True)


class RoomMicListener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 50
        self.recognizer.dynamic_energy_threshold = False
        self.is_recording = False
        self.audio_frames = []
        self.pre_buffer = collections.deque(maxlen=PRE_BUFFER_COUNT)
        self.silence_start = None

    def transcribe_and_send(self, frames):
        try:
            print(f"[ROOM-MIC] Transcribing {len(frames)*CHUNK_DURATION:.1f}s speech...", flush=True)
            raw_pcm = np.concatenate(frames)
            
            # Dynamic peak normalization for crystal-clear room speech
            peak = np.max(np.abs(raw_pcm))
            if peak > 30:
                gain = min(28000.0 / float(peak), 14.0)
                raw_pcm = np.clip(raw_pcm.astype(np.float32) * gain, -32768, 32767).astype(np.int16)

            audio_data = sr.AudioData(raw_pcm.tobytes(), SAMPLE_RATE, 2)
            
            raw_text = ""
            try:
                raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            except sr.UnknownValueError:
                try:
                    raw_text = self.recognizer.recognize_google(audio_data, language="en-US")
                except Exception:
                    raw_text = ""

            cleaned = raw_text.strip()
            if cleaned:
                safe_text = cleaned.encode("ascii", "ignore").decode("ascii")
                print(f"\n========================================", flush=True)
                print(f"  [YOU SAID]: \"{safe_text}\"", flush=True)
                print(f"========================================\n", flush=True)
                
                # 1. Update clipboard and inject keystrokes into Antigravity
                try:
                    import desktop_injector
                    desktop_injector.type_text_into_antigravity(cleaned)
                except Exception as e:
                    print(f"[ROOM-MIC Inject Error]: {e}", flush=True)

                # 2. Append to server stream
                append_to_conversation(cleaned)
            else:
                print("[ROOM-MIC] No words recognized.", flush=True)

        except Exception as e:
            print(f"[ROOM-MIC STT Error]: {e}", flush=True)

    def run(self):
        print("\n[ROOM-MIC] ========================================================", flush=True)
        print("[ROOM-MIC] Physical Background Microphone Listener Active on Windows!", flush=True)
        print("[ROOM-MIC] Auto-Typing & Auto-Send Enabled for Active Chat!", flush=True)
        print("[ROOM-MIC] Instant Voice Interruption / Barge-in: ENABLED", flush=True)
        print("[ROOM-MIC] ========================================================\n", flush=True)

        self.barge_in_streak = 0

        def audio_callback(indata, frames, time_info, status):
            try:
                audio_chunk = indata[:, 0].copy()
                rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
                threshold = load_threshold()

                # Deliberate speech detection
                if rms > threshold:
                    # Robust Barge-In: only interrupt if voice is sustained and intentional (RMS > 350 for 3 chunks)
                    if is_ai_speaking() and rms > max(threshold * 1.6, 350.0):
                        self.barge_in_streak += 1
                        if self.barge_in_streak >= 3:
                            request_stop_ai_playback()
                            self.barge_in_streak = 0
                    else:
                        self.barge_in_streak = 0

                    if not self.is_recording:
                        self.is_recording = True
                        self.audio_frames = list(self.pre_buffer)
                        self.silence_start = None
                        print(f"\n[ROOM-MIC] Voice detected (RMS: {rms:.1f})! Listening...", flush=True)

                    self.audio_frames.append(audio_chunk)
                    self.silence_start = None
                else:
                    self.barge_in_streak = 0
                    if not self.is_recording:
                        self.pre_buffer.append(audio_chunk)
                    else:
                        self.audio_frames.append(audio_chunk)
                        if self.silence_start is None:
                            self.silence_start = time.time()
                        elif time.time() - self.silence_start >= 1.2:
                            self.is_recording = False
                            captured = list(self.audio_frames)
                            self.audio_frames = []
                            self.silence_start = None
                            if len(captured) >= int(0.4 / CHUNK_DURATION):
                                threading.Thread(
                                    target=self.transcribe_and_send,
                                    args=(captured,),
                                    daemon=True
                                ).start()
            except Exception as e:
                pass

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            while True:
                time.sleep(0.1)


if __name__ == "__main__":
    listener = RoomMicListener()
    listener.run()


