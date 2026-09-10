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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPT_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
TEMP_AUDIO = os.path.join(BASE_DIR, "speech_seamless.mp3")


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

    start_time = time.time()
    update_live_state(is_speaking=True, current_text="Speaking...", stop_requested=False)
    winmm.mciSendStringW(f"play {alias}", None, 0, None)

    while True:
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms >= total_ms + 100:
            break

        if check_stop_requested(start_time):
            winmm.mciSendStringW(f"stop {alias}", None, 0, None)
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
            update_live_state(is_speaking=False, current_text="", stop_requested=False)
            print("\n[AUTO-SPEAKER] 🛑 Audio interrupted by user voice!", flush=True)
            break

        winmm.mciSendStringW(f"status {alias} mode", buf, 128, None)
        if buf.value in ("stopped", "") and elapsed_ms > 300:
            break

        time.sleep(0.03)

    winmm.mciSendStringW(f"close {alias}", None, 0, None)


def speak_sentence_stream(full_text):
    cleaned = clean_markdown_for_speech(full_text)
    if not cleaned:
        return

    settings = load_settings()
    if not settings.get("enabled", True):
        return

    voice_label = settings.get("voice", "en-GB-SoniaNeural")
    rate = settings.get("rate", "+12%")

    # Split into quick conversational chunks
    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if s.strip()]
    if not raw_sentences:
        raw_sentences = [cleaned]

    safe_msg = cleaned.encode("ascii", "ignore").decode("ascii")
    print(f"\n[AUTO-SPEAKER] Ultra-Fast Stream ({voice_label}, {rate}): \"{safe_msg[:60]}\"...", flush=True)

    # Concurrently pipeline sentence generation & playback
    audio_dir = os.path.join(BASE_DIR, "temp_audio")
    os.makedirs(audio_dir, exist_ok=True)

    for i, sent in enumerate(raw_sentences):
        chunk_file = os.path.join(audio_dir, f"chunk_{i % 3}.mp3")
        try:
            # Generate chunk
            asyncio.run(generate_seamless_speech(sent, settings, chunk_file))
            # Play chunk immediately
            play_audio(chunk_file)
        except Exception as e:
            print(f"[AUTO-SPEAKER] Chunk error: {e}", flush=True)

        if check_stop_requested(time.time()):
            break

    log_history(cleaned, voice_label)
    update_live_state(is_speaking=False, current_text="")


def monitor_and_read():
    print(f"[AUTO-SPEAKER] Ultra-Low Latency Voice Engine Active (20ms polling)...", flush=True)

    last_pos = 0
    if os.path.exists(TRANSCRIPT_LOG):
        with open(TRANSCRIPT_LOG, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            last_pos = f.tell()

    while True:
        try:
            if not os.path.exists(TRANSCRIPT_LOG):
                time.sleep(0.05)
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
                    speak_sentence_stream(content)

        except Exception as e:
            print(f"[AUTO-SPEAKER] Loop exception: {e}", flush=True)

        time.sleep(0.02)


if __name__ == "__main__":
    monitor_and_read()
