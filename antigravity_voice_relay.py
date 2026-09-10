"""
antigravity_voice_relay.py
Direct Two-Way Hands-Free Voice Relay for Antigravity Assistant.
Relays your spoken voice directly into this chat box, auto-submits,
and plays Antigravity replies seamlessly into your headphones.
"""

import os, sys, time, json, collections, threading, ctypes, pyperclip
import numpy as np, sounddevice as sd, speech_recognition as sr

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
    time.sleep(0.06)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.08)
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


def load_settings():
    default = {
        "voice": "en-GB-SoniaNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
        "energy_threshold": 45.0,
        "silence_timeout": 1.2
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


class AntigravityVoiceRelay:
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
            raw_pcm = np.concatenate(frames).tobytes()
            audio_data = sr.AudioData(raw_pcm, SAMPLE_RATE, 2)
            raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            cleaned = raw_text.strip()
            if cleaned:
                safe_text = cleaned.encode("ascii", "ignore").decode("ascii")
                print(f"\n[YOU SAID] >>> \"{safe_text}\"", flush=True)
                import desktop_injector
                desktop_injector.type_text_into_antigravity(cleaned)
                print("[SENT TO ANTIGRAVITY] Processing...\n", flush=True)
            else:
                print("[STT] No words recognized.", flush=True)
        except sr.UnknownValueError:
            print("[STT] (Audio unclear - speak slightly louder)", flush=True)
        except Exception as e:
            print(f"[STT Error]: {e}", flush=True)


    def start(self):
        print("\n=====================================================", flush=True)
        print("  ANTIGRAVITY DIRECT VOICE RELAY ACTIVE", flush=True)
        print("  1. Click your cursor inside this Antigravity chat box.", flush=True)
        print("  2. Wander around your room with headphones on.", flush=True)
        print("  3. Speak anytime -- it auto-types & responds directly!", flush=True)
        print("=====================================================\n", flush=True)

        def audio_callback(indata, frames, time_info, status):
            try:
                audio_chunk = indata[:, 0].copy()
                rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
                settings = load_settings()
                threshold = float(settings.get("energy_threshold", 45.0))
                silence_timeout = float(settings.get("silence_timeout", 1.2))

                if rms > threshold:
                    winmm.mciSendStringW("stop all", None, 0, None)
                    winmm.mciSendStringW("close all", None, 0, None)

                    if not self.is_recording:
                        self.is_recording = True
                        self.audio_frames = list(self.pre_buffer)
                        self.silence_start = None
                        print(f"\n[HEARING] Speaking (RMS: {rms:.1})...", flush=True)

                    self.audio_frames.append(audio_chunk)
                    self.silence_start = None
                else:
                    if not self.is_recording:
                        self.pre_buffer.append(audio_chunk)
                    else:
                        self.audio_frames.append(audio_chunk)
                        if self.silence_start is None:
                            self.silence_start = time.time()
                        elif time.time() - self.silence_start >= silence_timeout:
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
            except Exception:
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


def main():
    relay = AntigravityVoiceRelay()
    relay.start()


if __name__ == "__main__":
    main()
