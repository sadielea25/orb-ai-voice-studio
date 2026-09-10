"""
auto_voice_reader.py
Ultra-fluid, zero-gap natural conversational voice reader.
Synthesizes full responses in a single seamless audio pass with natural prosody.
"""

import os
import sys
import time
import json
import re
import asyncio
import ctypes

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

winmm = ctypes.windll.winmm

TRANSCRIPT_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_settings.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_history.json")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_live_state.json")
TEMP_AUDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_seamless.mp3")


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-GB-SoniaNeural",
        "rate": "+8%",  # Fluid natural UK conversational pace
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


def update_live_state(is_speaking=False, current_text=""):
    state = {
        "is_speaking": is_speaking,
        "current_text": current_text,
        "timestamp": time.time()
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


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


def clean_markdown_for_speech(text):
    if not text:
        return ""
    # Remove emoji & symbol ranges
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Convert markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove raw URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove markdown headers and list bullets
    text = re.sub(r"^[#>*\-]+\s*", "", text, flags=re.MULTILINE)
    # Remove markdown bold/italic asterisks
    text = re.sub(r"[*_~]+", "", text)
    # Remove XML/HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace into single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def generate_seamless_speech(text, settings, output_file):
    import edge_tts
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


def check_stop_requested():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("stop_requested", False)
        except Exception:
            pass
    return False


def play_audio(filepath):
    abs_path = os.path.abspath(filepath)
    alias = f"track_{int(time.time() * 1000) % 10000}"
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
    if ret != 0:
        return

    buf = ctypes.create_unicode_buffer(128)
    winmm.mciSendStringW(f"status {alias} length", buf, 128, None)
    try:
        total_ms = int(buf.value)
    except Exception:
        total_ms = 40000

    winmm.mciSendStringW(f"play {alias}", None, 0, None)
    start_time = time.time()

    while True:
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms >= total_ms + 100:
            break

        if check_stop_requested():
            winmm.mciSendStringW(f"stop {alias}", None, 0, None)
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
            print("\n[AUTO-SPEAKER] 🛑 Audio interrupted by user voice!", flush=True)
            break

        winmm.mciSendStringW(f"status {alias} mode", buf, 128, None)
        if buf.value in ("stopped", "") and elapsed_ms > 300:
            break

        time.sleep(0.03)

    winmm.mciSendStringW(f"close {alias}", None, 0, None)


def speak_full_response(full_text):
    cleaned = clean_markdown_for_speech(full_text)
    if not cleaned:
        return

    settings = load_settings()
    if not settings.get("enabled", True):
        return

    voice_label = settings.get("voice", "en-GB-SoniaNeural")
    rate = settings.get("rate", "+10%")

    safe_msg = cleaned.encode("ascii", "ignore").decode("ascii")
    print(f"\n[AUTO-SPEAKER] Speaking seamless ({voice_label}, {rate}): {safe_msg[:60]}...", flush=True)

    update_live_state(is_speaking=True, current_text=cleaned[:60])
    try:
        asyncio.run(generate_seamless_speech(cleaned, settings, TEMP_AUDIO))
        play_audio(TEMP_AUDIO)
        log_history(cleaned, voice_label)
    except Exception as e:
        print(f"[AUTO-SPEAKER] Error: {e}", flush=True)

    update_live_state(is_speaking=False, current_text="")


def monitor_and_read():
    print(f"[AUTO-SPEAKER] Seamless Zero-Gap Voice Engine Active...", flush=True)

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

                is_model = data.get("source") == "MODEL"
                is_response = data.get("type") == "PLANNER_RESPONSE"
                has_tools = bool(data.get("tool_calls"))
                content = data.get("content", "").strip()

                if is_model and is_response and not has_tools and content:
                    speak_full_response(content)

        except Exception as e:
            print(f"[AUTO-SPEAKER] Loop exception: {e}", flush=True)

        time.sleep(0.3)


if __name__ == "__main__":
    monitor_and_read()
