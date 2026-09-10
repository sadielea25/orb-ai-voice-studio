"""
voice_app_server.py
Production Two-Way Voice Server for Orb AI Assistant.
Zero-click, zero-paste hands-free conversation with instant natural British voice replies.
"""

import os
import sys
import json
import time
import re
import asyncio
import ctypes
import pyperclip
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import edge_tts

TRANSCRIPT_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web_app")
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
CONVERSATION_FILE = os.path.join(BASE_DIR, "live_conversation.json")
TEMP_AUDIO = os.path.join(BASE_DIR, "speech_test.mp3")
PORT = 8766

winmm = ctypes.windll.winmm


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-GB-SoniaNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "enabled": True,
        "handsfree_enabled": True,
        "auto_send": True,
        "energy_threshold": 45.0,
        "silence_timeout": 1.2,
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


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[SETTINGS] Error saving: {e}", flush=True)


def load_live_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"is_speaking": False, "current_text": ""}


def update_live_state(is_speaking=False, current_text=""):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "is_speaking": is_speaking,
                "current_text": current_text,
                "timestamp": time.time()
            }, f)
    except Exception:
        pass


def strip_ai_echo(text):
    if not text:
        return ""
    cleaned = text.strip()
    words_in = re.sub(r"[^a-z0-9\s]", " ", cleaned.lower()).split()
    if not words_in:
        return ""

    stopwords = {
        'a', 'an', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'it', 'is', 'be',
        'you', 'your', 'my', 'i', 'will', 'now', 'so', 'that', 'this', 'there', 'with', 'as', 'by',
        'are', 'was', 'were', 'have', 'has', 'had', 'do', 'does', 'did', 'all', 'any'
    }

    candidates = []
    state = load_live_state()
    curr = state.get("current_text", "").strip()
    is_speaking = state.get("is_speaking", False)
    state_time = state.get("timestamp", 0)

    if curr and len(curr) >= 8:
        candidates.append(curr)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                hist = json.load(f)
            for item in hist[:8]:
                t = item.get("text", "").strip()
                if t and len(t) >= 8 and t not in candidates:
                    candidates.append(t)
        except Exception:
            pass

    set_in = set(words_in)
    sig_in = set_in - stopwords

    # If AI was speaking recently (< 3 seconds ago) or is currently speaking
    speaking_recent = is_speaking or (time.time() - state_time < 3.0)

    for cand in candidates:
        words_cand = re.sub(r"[^a-z0-9\s]", " ", cand.lower()).split()
        if len(words_cand) < 3:
            continue

        set_cand = set(words_cand)
        sig_cand = set_cand - stopwords

        common_all = set_in & set_cand
        common_sig = sig_in & sig_cand

        overlap_all = len(common_all) / max(len(set_in), 1)
        overlap_sig = len(common_sig) / max(len(sig_in), 1) if sig_in else 0

        # Discard if significant word overlap or high general overlap
        if overlap_all >= 0.50 or (len(common_sig) >= 3 and overlap_sig >= 0.40):
            print(f"[ECHO-SHIELD] Discarded echo: '{cleaned}' (overlap_all={overlap_all:.2f}, common_sig={common_sig})", flush=True)
            return ""

        if speaking_recent and len(common_sig) >= 2 and overlap_sig >= 0.30:
            print(f"[ECHO-SHIELD] Discarded during recent playback: '{cleaned}'", flush=True)
            return ""

        # Check if the sentence ends with a sequence of words from cand
        cand_str = " ".join(words_cand)
        in_str = " ".join(words_in)
        for seq_len in range(min(len(words_cand), 8), 3, -1):
            seq = " ".join(words_cand[:seq_len])
            if seq in in_str:
                idx = in_str.find(seq)
                words_before = in_str[:idx].strip().split()
                orig_words = cleaned.split()
                if len(words_before) > 0:
                    return " ".join(orig_words[:len(words_before)]).strip()
                return ""

    return cleaned


def is_echo_of_ai(text):
    if not text:
        return True
    cleaned = strip_ai_echo(text)
    if not cleaned or len(re.sub(r"[^a-z0-9]", "", cleaned.lower())) < 3:
        return True
    return False


def get_conversation_history(limit=30):
    messages = []
    if os.path.exists(TRANSCRIPT_LOG):
        try:
            with open(TRANSCRIPT_LOG, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    src = d.get("source")
                    typ = d.get("type")
                    cnt = d.get("content", "")
                    if not isinstance(cnt, str) or not cnt.strip():
                        continue
                    
                    if typ == "USER_INPUT" or src == "USER_EXPLICIT":
                        t_str = d.get("created_at", "")
                        if "T" in t_str:
                            t_str = t_str.split("T")[1].split(".")[0][:5]
                        else:
                            t_str = time.strftime("%H:%M")
                        messages.append({
                            "role": "user",
                            "text": cnt.strip(),
                            "time": t_str
                        })
                    elif src == "MODEL" and typ == "PLANNER_RESPONSE" and not d.get("tool_calls"):
                        t_str = d.get("created_at", "")
                        if "T" in t_str:
                            t_str = t_str.split("T")[1].split(".")[0][:5]
                        else:
                            t_str = time.strftime("%H:%M")
                        messages.append({
                            "role": "assistant",
                            "text": cnt.strip(),
                            "time": t_str
                        })
        except Exception:
            pass

    if os.path.exists(CONVERSATION_FILE):
        try:
            with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
                live_msgs = json.load(f)
                for lm in live_msgs:
                    if lm not in messages:
                        messages.append(lm)
        except Exception:
            pass

    return messages[-limit:]


def append_to_live_conversation(role, text):
    msgs = []
    if os.path.exists(CONVERSATION_FILE):
        try:
            with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
                msgs = json.load(f)
        except Exception:
            msgs = []
    msgs.append({
        "role": role,
        "text": text,
        "time": time.strftime("%H:%M")
    })
    msgs = msgs[-40:]
    try:
        with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
            json.dump(msgs, f, indent=2)
    except Exception:
        pass


# All voice input goes 100% directly to Antigravity Agent (zero secondary AI bots)


async def generate_speech(text, settings, output_path):
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
    await communicate.save(output_path)


def play_audio(filepath):
    abs_path = os.path.abspath(filepath)
    alias = f"test_{int(time.time() * 1000) % 10000}"
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
    if ret == 0:
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        winmm.mciSendStringW(f"close {alias}", None, 0, None)


def speak_and_log_reply(reply_text):
    settings = load_settings()
    update_live_state(is_speaking=True, current_text=reply_text[:60])
    try:
        asyncio.run(generate_speech(reply_text, settings, TEMP_AUDIO))
        play_audio(TEMP_AUDIO)
    except Exception as e:
        print(f"[REPLY-SPEECH-ERR]: {e}", flush=True)
    update_live_state(is_speaking=False, current_text="")


class PWAHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        url_path = self.path.split("?")[0]
        if url_path == "/" or url_path == "/index.html":
            file_path = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content.encode("utf-8"))
            else:
                self._set_headers(404)
        elif url_path == "/manifest.json":
            file_path = os.path.join(WEB_DIR, "manifest.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "application/manifest+json")
                self.wfile.write(content.encode("utf-8"))
            else:
                self._set_headers(404)
        elif url_path == "/sw.js":
            file_path = os.path.join(WEB_DIR, "sw.js")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "application/javascript")
                self.wfile.write(content.encode("utf-8"))
        elif url_path == "/api/settings":
            settings = load_settings()
            self._set_headers(200)
            self.wfile.write(json.dumps(settings).encode("utf-8"))
        elif url_path == "/api/status":
            state = load_live_state()
            self._set_headers(200)
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif url_path == "/api/conversation":
            conv = get_conversation_history(30)
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": conv}).encode("utf-8"))
        elif url_path == "/api/audio_preview":
            if os.path.exists(TEMP_AUDIO):
                with open(TEMP_AUDIO, "rb") as f:
                    audio_data = f.read()
                self._set_headers(200, "audio/mpeg")
                self.wfile.write(audio_data)
            else:
                self._set_headers(404)
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if self.path == "/api/settings":
            settings = load_settings()
            settings.update(data)
            save_settings(settings)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "saved", "settings": settings}).encode("utf-8"))

        elif self.path == "/api/speech_input":
            text = data.get("text", "").strip()
            source = data.get("source", "app")
            if text:
                stripped_text = strip_ai_echo(text)
                if not stripped_text:
                    safe_raw = text.encode("ascii", "ignore").decode("ascii")
                    print(f"[VOICE-RELAY] [ECHO-SHIELD] Discarded 100% echo ({source}): '{safe_raw}'", flush=True)
                    self._set_headers(200)
                    self.wfile.write(b'{"status": "echo_ignored"}')
                    return

                text = stripped_text
                safe_text = text.encode("ascii", "ignore").decode("ascii")
                print(f"[VOICE-RELAY] Speech input ({source}): '{safe_text}'", flush=True)
                append_to_live_conversation("user", text)

                # If speech originated from the Web App / PWA, inject directly into Antigravity chat
                if source != "room_mic":
                    try:
                        import desktop_injector
                        desktop_injector.type_text_into_antigravity(text)
                    except Exception as e:
                        print(f"[VOICE-RELAY-ERR]: {e}", flush=True)

            self._set_headers(200)
            self.wfile.write(b'{"status": "received"}')

        elif self.path == "/api/stop":
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            update_live_state(is_speaking=False)
            self._set_headers(200)
            self.wfile.write(b'{"status": "stopped"}')

        elif self.path == "/api/test":
            text = data.get("text", "Hello Sadie! This is your voice preview.")
            settings = load_settings()
            try:
                asyncio.run(generate_speech(text, settings, TEMP_AUDIO))
                play_audio(TEMP_AUDIO)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "spoken", "has_audio": True}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')

    def log_message(self, format, *args):
        return


def run():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, PWAHandler)
    print(f"Orb AI Voice Assistant live at http://localhost:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    run()

