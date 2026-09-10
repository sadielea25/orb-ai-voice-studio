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


def is_echo_of_ai(text):
    if not text:
        return False
    # Only reject if text is an exact match or AI text STARTS WITH user text (near-verbatim repeat)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            curr = state.get("current_text", "").strip().lower()
            t_lower = text.strip().lower()
            # Must be at least 15 chars and be an exact match or AI text starts with user text
            if curr and len(t_lower) >= 15:
                if t_lower == curr or curr.startswith(t_lower):
                    return True
        except Exception:
            pass
    return False


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
            raw_pcm = np.concatenate(frames)
            duration_s = len(raw_pcm) / SAMPLE_RATE
            print(f"[ROOM-MIC] Transcribing {duration_s:.1f}s of audio (peak: {np.max(np.abs(raw_pcm))})...", flush=True)

            # Downsample from 44100 Hz to 16000 Hz for Google STT
            ratio = STT_RATE / SAMPLE_RATE  # 0.3628...
            target_len = int(len(raw_pcm) * ratio)
            indices = np.linspace(0, len(raw_pcm) - 1, target_len).astype(np.int32)
            resampled = raw_pcm[indices]

            audio_data = sr.AudioData(resampled.tobytes(), STT_RATE, 2)

            raw_text = ""
            try:
                raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            except sr.UnknownValueError:
                print("[ROOM-MIC] Google STT: could not understand audio (en-GB), trying en-US...", flush=True)
                try:
                    raw_text = self.recognizer.recognize_google(audio_data, language="en-US")
                except sr.UnknownValueError:
                    print("[ROOM-MIC] Google STT: could not understand audio (en-US either). Skipping.", flush=True)
                    raw_text = ""
                except Exception as e:
                    print(f"[ROOM-MIC] Google STT network error (en-US): {e}", flush=True)
                    raw_text = ""
            except Exception as e:
                print(f"[ROOM-MIC] Google STT network error (en-GB): {e}", flush=True)
                raw_text = ""

            cleaned = raw_text.strip()
            if cleaned:
                # Echo Rejection: Check if Google STT transcribed the AI's own speaker output
                if is_echo_of_ai(cleaned):
                    print(f"\n[ROOM-MIC] 🔇 Ignored speaker acoustic echo: \"{cleaned}\"", flush=True)
                    return

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

        except Exception as e:
            print(f"[ROOM-MIC STT Error]: {e}", flush=True)

    def run(self):
        print("\n[ROOM-MIC] ========================================================", flush=True)
        print("[ROOM-MIC] Physical Background Microphone Listener Active on Windows!", flush=True)
        print("[ROOM-MIC] Auto-Typing & Auto-Send Enabled for Active Chat!", flush=True)
        print("[ROOM-MIC] Echo Cancellation & Seamless Barge-In: ENABLED", flush=True)
        print("[ROOM-MIC] ========================================================\n", flush=True)

        self.last_ai_speech_time = 0.0

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

                # Speaker Shield: While AI is speaking, completely discard audio frames
                # Speaker output through mic is loud (RMS 500-2000) and was previously falsely triggering barge-in, cutting AI off mid-sentence
                if ai_active:
                    self.last_ai_speech_time = time.time()
                    self.is_recording = False
                    self.audio_frames = []
                    self.pre_buffer.clear()
                    return

                # Reverb guard: 0.35s after AI speech finishes, ignore decaying room acoustics
                if time.time() - self.last_ai_speech_time < 0.35:
                    self.pre_buffer.clear()
                    return

                # User speech detection when AI is not speaking
                if rms > threshold:
                    if not self.is_recording:
                        self.is_recording = True
                        self.audio_frames = list(self.pre_buffer)
                        self.silence_start = None
                        print(f"\n[ROOM-MIC] Voice detected (RMS: {rms:.1f})! Listening...", flush=True)

                    self.audio_frames.append(audio_chunk)
                    self.silence_start = None

                    # Max duration cut (6s max per sentence to prevent hanging)
                    if len(self.audio_frames) * CHUNK_DURATION >= 6.0:
                        self.is_recording = False
                        captured = list(self.audio_frames)
                        self.audio_frames = []
                        self.silence_start = None
                        threading.Thread(
                            target=self.transcribe_and_send,
                            args=(captured,),
                            daemon=True
                        ).start()
                else:
                    if not self.is_recording:
                        self.pre_buffer.append(audio_chunk)
                    else:
                        self.audio_frames.append(audio_chunk)
                        if self.silence_start is None:
                            self.silence_start = time.time()
                        elif time.time() - self.silence_start >= 0.75:
                            self.is_recording = False
                            captured = list(self.audio_frames)
                            self.audio_frames = []
                            self.silence_start = None
                            if len(captured) >= int(0.3 / CHUNK_DURATION):
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


