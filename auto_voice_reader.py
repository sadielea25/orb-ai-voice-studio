"""
auto_voice_reader.py
Ultra-fluid, direct hardware conversational voice reader.
Uses miniaudio + sounddevice for instantaneous auto-switching between Headphones (budi 50) and Laptop Speakers (Realtek).
"""

import os
import sys
import time
import json
import re
import asyncio
import collections
import threading
import edge_tts
import miniaudio
import numpy as np
import sounddevice as sd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPT_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-GB-SoniaNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "enabled": True,
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


def update_live_state(is_speaking=False, current_text="", stop_requested=False):
    state = {
        "is_speaking": is_speaking,
        "current_text": current_text,
        "stop_requested": stop_requested,
        "timestamp": time.time()
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def check_stop_requested(playback_start_time):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("stop_requested", False):
                    ts = data.get("timestamp", 0)
                    if ts >= playback_start_time - 0.1:
                        return True
        except Exception:
            pass
    return False


def get_active_output_device():
    """
    Dynamically finds the best physical output device:
    1. budi 50 / Bluetooth Headphones if connected
    2. Physical Realtek Speakers (laptop speakers)
    3. System default output
    """
    try:
        devices = sd.query_devices()
        budi_idx = None
        realtek_idx = None
        default_out = sd.default.device[1]

        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0:
                name = d.get("name", "").lower()
                if "budi" in name:
                    budi_idx = i
                    break

        if budi_idx is not None:
            return budi_idx, devices[budi_idx]["name"]
        return None, "System Default"
    except Exception:
        return None, "System Default"


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


async def synthesize_speech_pcm(text, settings):
    voice = settings.get("voice", "en-GB-SoniaNeural")
    rate = settings.get("rate", "+10%")
    pitch = settings.get("pitch", "+0Hz")
    volume = settings.get("volume", "+0%")

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume
    )

    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    if not audio_bytes:
        return None

    decoded = miniaudio.decode(
        audio_bytes,
        nchannels=2,
        sample_rate=44100,
        output_format=miniaudio.SampleFormat.SIGNED16
    )
    pcm = np.frombuffer(decoded.samples, dtype=np.int16).reshape(-1, 2)
    return pcm


def play_audio_pcm(pcm_data):
    if pcm_data is None or len(pcm_data) == 0:
        return

    dev_idx, dev_name = get_active_output_device()
    start_time = time.time()
    update_live_state(is_speaking=True, current_text="Speaking...", stop_requested=False)

    try:
        if dev_idx is not None:
            try:
                sd.play(pcm_data, samplerate=44100, device=dev_idx)
            except Exception:
                sd.play(pcm_data, samplerate=44100)
        else:
            sd.play(pcm_data, samplerate=44100)

        duration = len(pcm_data) / 44100.0
        elapsed = 0.0

        while elapsed < duration:
            if check_stop_requested(start_time):
                sd.stop()
                update_live_state(is_speaking=False, current_text="", stop_requested=False)
                print("\n[AUTO-SPEAKER] 🛑 Audio interrupted by user voice!", flush=True)
                return
            time.sleep(0.04)
            elapsed = time.time() - start_time

        sd.wait()
        time.sleep(0.35)
    except Exception as e:
        print(f"[AUTO-SPEAKER] Playback error: {e}", flush=True)

    update_live_state(is_speaking=False, current_text="")


def log_history(text, voice_label):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.insert(0, {
        "text": text,
        "voice": voice_label,
        "time": time.strftime("%H:%M:%S")
    })
    history = history[:25]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def speak_full_response(full_text):
    cleaned = clean_markdown_for_speech(full_text)
    if not cleaned:
        return

    settings = load_settings()
    if not settings.get("enabled", True):
        return

    voice_label = settings.get("voice", "en-GB-SoniaNeural")
    dev_idx, dev_name = get_active_output_device()
    safe_msg = cleaned.encode("ascii", "ignore").decode("ascii")
    print(f"\n[AUTO-SPEAKER] Output -> {dev_name} | {voice_label}: \"{safe_msg[:60]}\"...", flush=True)

    update_live_state(is_speaking=True, current_text=cleaned, stop_requested=False)
    log_history(cleaned, voice_label)

    try:
        pcm = asyncio.run(synthesize_speech_pcm(cleaned, settings))
        play_audio_pcm(pcm)
    except Exception as e:
        print(f"[AUTO-SPEAKER] Synthesis/Playback Error: {e}", flush=True)

    update_live_state(is_speaking=False, current_text="")


def monitor_and_read():
    print(f"[AUTO-SPEAKER] Direct Hardware Voice Engine Active (Sounddevice + Miniaudio)...", flush=True)

    last_pos = 0
    if os.path.exists(TRANSCRIPT_LOG):
        try:
            with open(TRANSCRIPT_LOG, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                last_pos = f.tell()
        except Exception:
            last_pos = 0

    seen_hashes = collections.deque(maxlen=100)

    while True:
        try:
            if not os.path.exists(TRANSCRIPT_LOG):
                time.sleep(0.05)
                continue

            current_size = os.path.getsize(TRANSCRIPT_LOG)
            if current_size < last_pos:
                last_pos = 0

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

                is_model = data.get("source") == "MODEL"
                is_response = data.get("type") == "PLANNER_RESPONSE"
                has_tools = bool(data.get("tool_calls"))
                content = data.get("content", "").strip()

                if is_model and is_response and not has_tools and content:
                    msg_hash = hash(content[:150])
                    if msg_hash not in seen_hashes:
                        seen_hashes.append(msg_hash)
                        speak_full_response(content)

        except Exception as e:
            print(f"[AUTO-SPEAKER] Loop exception: {e}", flush=True)

        time.sleep(0.02)


if __name__ == "__main__":
    monitor_and_read()
