"""
handsfree_duplex.py
Full-Duplex Hands-Free Conversational Engine for Headphones & Room Walking.
Run this directly on your Windows desktop (Session 1) for 100% reliable physical typing & speech.
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
import edge_tts
import ctypes
import winsound
import asyncio

pyautogui.FAILSAFE = False

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

winmm = ctypes.windll.winmm
TRANSCRIPT_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_settings.json")
TEMP_AUDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_duplex.mp3")

SAMPLE_RATE = 44100
CHUNK_DURATION = 0.05
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

is_speaking_ai = False
is_listening_user = False


def load_settings():
    default = {
        "voice": "en-GB-SoniaNeural",
        "rate": "+8%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "silence_timeout": 1.6,
        "energy_threshold": 350.0
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


def clean_markdown_for_speech(text):
    if not text:
        return ""
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^[#>*\-]+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~]+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_user_transcription(text):
    if not text:
        return ""
    text = text.strip()
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    text = re.sub(r"^(um+|uh+|er+|like)\s*,?\s*", "", text, flags=re.IGNORECASE)
    if text and text[-1] not in ".?!":
        text += "."
    return text


async def generate_speech_file(text, settings, output_file):
    voice = settings.get("voice", "en-GB-SoniaNeural")
    rate = settings.get("rate", "+8%")
    pitch = settings.get("pitch", "+0Hz")
    volume = settings.get("volume", "+0%")
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume
    )
    await communicate.save(output_file)


def play_audio_file(filepath):
    abs_path = os.path.abspath(filepath)
    alias = f"duplex_{int(time.time() * 1000) % 10000}"
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
    if ret == 0:
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        winmm.mciSendStringW(f"close {alias}", None, 0, None)


def speak_ai_reply(raw_text):
    global is_speaking_ai
    cleaned = clean_markdown_for_speech(raw_text)
    if not cleaned:
        return

    is_speaking_ai = True
    settings = load_settings()
    safe_msg = cleaned.encode("ascii", "ignore").decode("ascii")
    print(f"\n[AI SPEAKING] >>> {safe_msg[:80]}...", flush=True)

    try:
        asyncio.run(generate_speech_file(cleaned, settings, TEMP_AUDIO))
        play_audio_file(TEMP_AUDIO)
    except Exception as e:
        print(f"[AI SPEAKING] Error: {e}", flush=True)

    time.sleep(0.3)
    is_speaking_ai = False
    print("\n[READY] Listening for your voice...", flush=True)


def ai_transcript_listener_thread():
    print("[DUPLEX] AI Voice Output Listener active...", flush=True)
    last_pos = 0
    if os.path.exists(TRANSCRIPT_LOG):
        with open(TRANSCRIPT_LOG, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            last_pos = f.tell()

    while True:
        try:
            if not os.path.exists(TRANSCRIPT_LOG):
                time.sleep(0.3)
                continue

            with open(TRANSCRIPT_LOG, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                last_pos = f.tell()

            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                if data.get("source") == "MODEL" and data.get("type") == "PLANNER_RESPONSE" and not data.get("tool_calls"):
                    content = data.get("content", "").strip()
                    if content:
                        speak_ai_reply(content)
        except Exception as e:
            print(f"[AI LISTENER ERROR]: {e}", flush=True)

        time.sleep(0.3)


user32 = ctypes.windll.user32
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


class PhysicalMicEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 50
        self.recognizer.dynamic_energy_threshold = False
        self.is_recording = False
        self.audio_frames = []
        self.pre_buffer = collections.deque(maxlen=6)
        self.silence_start = None

    def transcribe_and_send(self, frames):
        global is_speaking_ai
        try:
            print("\n[STT] Transcribing your voice...", flush=True)
            raw_pcm = np.concatenate(frames).tobytes()
            audio_data = sr.AudioData(raw_pcm, SAMPLE_RATE, 2)
            raw_text = self.recognizer.recognize_google(audio_data, language="en-GB")
            cleaned = clean_user_transcription(raw_text)
            safe_text = cleaned.encode("ascii", "ignore").decode("ascii")
            print(f"\n[YOU SAID] >>> \"{safe_text}\"", flush=True)

            if cleaned:
                try:
                    winsound.Beep(1200, 80)
                except Exception:
                    pass

                pyperclip.copy(cleaned)
                send_windows_paste_and_enter()
                print(f"[SENT] Successfully typed and sent to chat!", flush=True)

        except sr.UnknownValueError:
            print("[STT] (Audio unclear - speak slightly louder)", flush=True)
        except Exception as e:
            print(f"[STT Error]: {e}", flush=True)

    def start_listening(self):
        print("\n=======================================================")
        print("  HANDS-FREE CONVERSATION ACTIVE (DESKTOP MODE)")
        print("  1. Click your cursor inside this Antigravity chat box.")
        print("  2. Wander around your room with your headphones on.")
        print("  3. Speak anytime — it types, sends, and speaks back!")
        print("=======================================================\n", flush=True)

        speak_ai_reply("Hands-free room mode is active. You can wander around the room and talk to me naturally.")

        def audio_callback(indata, frames, time_info, status):
            global is_speaking_ai

            audio_chunk = indata[:, 0].copy()
            rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
            settings = load_settings()
            threshold = float(settings.get("energy_threshold", 45.0))
            silence_timeout = float(settings.get("silence_timeout", 1.2))

            if rms > threshold:
                if is_speaking_ai:
                    winmm.mciSendStringW("stop all", None, 0, None)
                    winmm.mciSendStringW("close all", None, 0, None)
                    is_speaking_ai = False

                if not self.is_recording:
                    self.is_recording = True
                    self.audio_frames = list(self.pre_buffer)
                    self.silence_start = None
                    print(f"\n[HEARING YOU] Speaking (RMS: {rms:.1f})...", flush=True)

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
    t = threading.Thread(target=ai_transcript_listener_thread, daemon=True)
    t.start()

    engine = PhysicalMicEngine()
    engine.start_listening()


if __name__ == "__main__":
    main()
