"""
handsfree_voice_engine.py
Ultra-reliable room voice activity detection with FAILSAFE=False and multi-method typing injection.
"""

import os
import sys
import time
import json
import re
import io
import wave
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import pyperclip
import pyautogui

# Safeguards
pyautogui.FAILSAFE = False

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_settings.json")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_live_state.json")

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.05
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)


def load_settings():
    default = {
        "handsfree_enabled": True,
        "auto_send": True,
        "silence_timeout": 1.6,
        "energy_threshold": 300.0,
        "language": "en-GB"
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


def is_ai_speaking():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("is_speaking", False)
        except Exception:
            pass
    return False


def update_stt_state(state_name, last_text=""):
    try:
        current = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
        current["stt_state"] = state_name
        if last_text:
            current["last_user_speech"] = last_text
        current["stt_timestamp"] = time.time()
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f)
    except Exception:
        pass


def clean_transcription(text):
    if not text:
        return ""
    text = text.strip()
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    text = re.sub(r"^(um+|uh+|er+|like)\s*,?\s*", "", text, flags=re.IGNORECASE)
    if text and text[-1] not in ".?!":
        text += "."
    return text


def inject_text_into_active_window(text, auto_send=True):
    if not text:
        return
    safe_preview = text.encode("ascii", "ignore").decode("ascii")
    print(f"\n[INJECTOR] Injected to active window: '{safe_preview}' (Auto-send: {auto_send})", flush=True)
    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)
        if auto_send:
            pyautogui.press("enter")
    except Exception as e:
        print(f"[INJECTOR] Error: {e}", flush=True)


class HandsFreeEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.running = True
        self.is_recording = False
        self.audio_frames = []
        self.silence_start = None

    def pcm_to_audio_data(self, frames):
        raw_np = np.concatenate(frames).astype(np.float32)
        peak = np.max(np.abs(raw_np))
        if peak > 40.0:
            gain = 28000.0 / peak
            raw_np = np.clip(raw_np * gain, -32767, 32767)
        raw_int16 = raw_np.astype(np.int16).tobytes()

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(raw_int16)
        wav_io.seek(0)
        with sr.AudioFile(wav_io) as source:
            return self.recognizer.record(source)

    def transcribe_and_inject(self, frames, settings):
        try:
            update_stt_state("processing")
            print("\n[STT] Processing audio...", flush=True)
            audio_data = self.pcm_to_audio_data(frames)
            lang = settings.get("language", "en-GB")
            raw_text = self.recognizer.recognize_google(audio_data, language=lang)
            cleaned = clean_transcription(raw_text)
            safe_text = cleaned.encode("ascii", "ignore").decode("ascii")
            print(f"[STT] Transcribed: \"{safe_text}\"", flush=True)
            update_stt_state("transcribed", cleaned)

            if cleaned:
                inject_text_into_active_window(cleaned, auto_send=settings.get("auto_send", True))
        except sr.UnknownValueError:
            print("[STT] (Audio unclear)", flush=True)
            update_stt_state("listening")
        except Exception as e:
            print(f"[STT] Recognition error: {e}", flush=True)
            update_stt_state("listening")

    def run(self):
        print("[HANDS-FREE] Room Voice Engine active with FAILSAFE=False...", flush=True)
        update_stt_state("listening")

        def audio_callback(indata, frames, time_info, status):
            if not self.running:
                return

            settings = load_settings()
            if not settings.get("handsfree_enabled", True):
                if self.is_recording:
                    self.is_recording = False
                    self.audio_frames = []
                return

            if is_ai_speaking():
                if self.is_recording:
                    self.is_recording = False
                    self.audio_frames = []
                update_stt_state("ai_speaking")
                return

            audio_chunk = indata[:, 0]
            rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
            threshold = float(settings.get("energy_threshold", 300.0))
            silence_timeout = float(settings.get("silence_timeout", 1.6))

            if rms > threshold:
                if not self.is_recording:
                    self.is_recording = True
                    self.audio_frames = []
                    self.silence_start = None
                    update_stt_state("user_speaking")
                    print(f"\n[HANDS-FREE] Voice detected! Listening...", flush=True)
                self.audio_frames.append(audio_chunk.copy())
                self.silence_start = None
            else:
                if self.is_recording:
                    self.audio_frames.append(audio_chunk.copy())
                    if self.silence_start is None:
                        self.silence_start = time.time()
                    elif time.time() - self.silence_start >= silence_timeout:
                        self.is_recording = False
                        captured = list(self.audio_frames)
                        self.audio_frames = []
                        self.silence_start = None
                        if len(captured) >= int(0.6 / CHUNK_DURATION):
                            threading.Thread(
                                target=self.transcribe_and_inject,
                                args=(captured, settings),
                                daemon=True
                            ).start()
                        else:
                            update_stt_state("listening")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=audio_callback
        ):
            while self.running:
                time.sleep(0.1)


if __name__ == "__main__":
    engine = HandsFreeEngine()
    engine.run()
