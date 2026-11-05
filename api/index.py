"""
api/index.py
Vercel Serverless Function for Orb AI Live Voice Studio Cloud API.
Provides high-performance cloud voice synthesis, Gemini AI conversation, and settings sync.
"""

from http.server import BaseHTTPRequestHandler
import os
import io
import json
import asyncio
import urllib.parse
import urllib.request
import base64
import time

VOICE_SETTINGS = {
    "engine": "edge",
    "voice": "en-GB-SoniaNeural",
    "rate": "+10%",
    "pitch": "+0Hz",
    "volume": "+0%",
    "enabled": True,
    "handsfree_enabled": True,
    "auto_send": True,
    "energy_threshold": 45.0,
    "silence_timeout": 5.0
}

CONVERSATION_HISTORY = [
    {
        "role": "assistant",
        "text": "Hello Sadie! Orb AI Voice Studio v2.9 is live and connected in the cloud.",
        "time": time.strftime("%H:%M")
    }
]

DEFAULT_GEM_KEY = base64.b64decode("QVEuQWI4Uk42TGhSSUo4WF9QT2JkMWozaXVYQm9JSkNOVjRuMzBrakMyVXh6RzZZQVU4U2c=").decode()


def generate_audio_bytes(text, voice_id="en-GB-SoniaNeural"):
    """
    Synthesizes speech to MP3 bytes.
    Tries edge-tts first; falls back smoothly to gTTS (Google Translate TTS)
    with native British (co.uk) or Irish (ie) accent if edge-tts is blocked on cloud datacenter IPs.
    """
    clean_text = text.strip()
    if not clean_text:
        return b""

    # Attempt 1: Edge-TTS
    try:
        import edge_tts
        async def _edge():
            comm = edge_tts.Communicate(clean_text, voice_id)
            buf = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
            return buf
        audio_data = asyncio.run(_edge())
        if audio_data and len(audio_data) > 100:
            return audio_data
    except Exception:
        pass

    # Attempt 2: High-reliability Google TTS (gTTS)
    try:
        from gtts import gTTS
        tld = "co.uk"
        v_low = voice_id.lower()
        if "ie" in v_low or "emily" in v_low or "connor" in v_low:
            tld = "ie"
        elif "us" in v_low or "ava" in v_low or "brian" in v_low:
            tld = "com"
        tts = gTTS(text=clean_text, lang="en", tld=tld)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except Exception as e:
        print("[TTS-ERROR]:", e, flush=True)
        return b""


def query_gemini(prompt, history=None, context=None):
    """Queries Google Gemini model with conversational instructions."""
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-2.5-flash-lite"]

    sys_prompt = (
        "You are Orb, an elite conversational AI voice assistant for Sadie. "
        "Keep responses natural, crisp, intelligent, and meant to be spoken aloud. "
        "Strictly adhere to UK English spelling and vocabulary. "
        "Never use exclamation marks. Keep replies concise (1-2 clear sentences) unless explicitly asked for detail."
    )

    contents = []
    if history:
        for msg in history[-8:]:
            role = "user" if msg.get("role") == "user" else "model"
            txt = msg.get("text", "").strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt}]})

    user_text = prompt
    if context:
        user_text = f"Context: {context}\n\nUser: {prompt}"

    contents.append({"role": "user", "parts": [{"text": user_text}]})

    payload = {
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.6}
    }

    for mod in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=7) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                cand = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if cand:
                    cand = cand.replace("!", ".")
                    return cand
        except Exception:
            continue

    return "I am connected, but I could not reach the language servers just now."


class handler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Access-Control-Allow-Private-Network")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        q = urllib.parse.parse_qs(parsed.query)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        api_dir = os.path.dirname(os.path.abspath(__file__))

        if path in ("/", "/index.html"):
            for candidate in [
                os.path.join(base_dir, "public", "index.html"),
                os.path.join(base_dir, "web_app", "index.html"),
                os.path.join(api_dir, "index.html"),
                os.path.join(os.getcwd(), "public", "index.html")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "text/html; charset=utf-8")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif path == "/manifest.json":
            for candidate in [
                os.path.join(base_dir, "public", "manifest.json"),
                os.path.join(base_dir, "web_app", "manifest.json"),
                os.path.join(api_dir, "manifest.json")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/manifest+json")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif path == "/sw.js":
            for candidate in [
                os.path.join(base_dir, "public", "sw.js"),
                os.path.join(base_dir, "web_app", "sw.js"),
                os.path.join(api_dir, "sw.js")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/javascript")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif path in ("/api/status", "/status"):
            state = {
                "status": "online",
                "mode": "cloud",
                "app_version": "v2.9",
                "active_chat_title": "Orb AI Cloud Studio",
                "is_speaking": False,
                "enabled": VOICE_SETTINGS.get("enabled", True),
                "voice": VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(state).encode("utf-8"))
            return

        elif path in ("/api/settings", "/settings"):
            self._set_headers(200)
            self.wfile.write(json.dumps(VOICE_SETTINGS).encode("utf-8"))
            return

        elif path in ("/api/conversation", "/conversation"):
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": CONVERSATION_HISTORY}).encode("utf-8"))
            return

        elif path in ("/api/tts", "/tts"):
            text = q.get("text", [""])[0].strip()
            voice = q.get("voice", [VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")])[0].strip()
            if not text:
                self._set_headers(400)
                self.wfile.write(b'{"error": "No text provided"}')
                return
            audio_bytes = generate_audio_bytes(text, voice)
            if audio_bytes:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(audio_bytes)
            else:
                self._set_headers(500)
                self.wfile.write(b'{"error": "Audio generation failed"}')
            return

        elif path in ("/api/voice_preview_audio", "/voice_preview_audio"):
            voice = q.get("voice", ["en-GB-SoniaNeural"])[0].strip()
            preview_text = "Hello Sadie, this is your British voice preview."
            if "IE" in voice or "Emily" in voice or "Connor" in voice:
                preview_text = "Hello Sadie, this is your Irish voice preview."
            elif "US" in voice:
                preview_text = "Hello Sadie, this is your American voice preview."
            audio_bytes = generate_audio_bytes(preview_text, voice)
            if audio_bytes:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(audio_bytes)
            else:
                self._set_headers(500)
                self.wfile.write(b'{"error": "Voice preview failed"}')
            return

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "app": "Orb AI Live Voice Studio",
            "version": "v2.9",
            "status": "online",
            "cloud": True
        }).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        path = self.path.split("?")[0]

        if path in ("/api/speech_input", "/speech_input"):
            user_text = data.get("text", "").strip()
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            if not user_text:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ok", "reply": ""}')
                return

            CONVERSATION_HISTORY.append({
                "role": "user",
                "text": user_text,
                "time": time.strftime("%H:%M")
            })

            ai_reply = query_gemini(user_text, history=CONVERSATION_HISTORY)
            CONVERSATION_HISTORY.append({
                "role": "assistant",
                "text": ai_reply,
                "time": time.strftime("%H:%M")
            })

            audio_url = f"/api/tts?text={urllib.parse.quote(ai_reply)}&voice={urllib.parse.quote(voice)}"
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "reply": ai_reply,
                "audio_url": audio_url
            }).encode("utf-8"))
            return

        elif path in ("/api/read_ai_reply", "/api/speak_last", "/read_ai_reply", "/speak_last"):
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            last_reply = ""
            for msg in reversed(CONVERSATION_HISTORY):
                if msg.get("role") == "assistant" and msg.get("text"):
                    last_reply = msg["text"]
                    break
            if not last_reply:
                last_reply = "Orb AI is online and ready to assist you."

            audio_url = f"/api/tts?text={urllib.parse.quote(last_reply)}&voice={urllib.parse.quote(voice)}"
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "reply": last_reply,
                "audio_url": audio_url
            }).encode("utf-8"))
            return

        elif path in ("/api/polish_text", "/polish_text"):
            raw_text = data.get("text", "").strip()
            if not raw_text:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ok", "polished": ""}')
                return
            context = data.get("context", "")
            polished = query_gemini(
                f"Please polish this spoken draft into articulate, professional UK English without filler words:\n\"{raw_text}\"",
                context=context
            )
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "polished": polished}).encode("utf-8"))
            return

        elif path in ("/api/settings", "/settings"):
            VOICE_SETTINGS.update(data)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "saved", "settings": VOICE_SETTINGS}).encode("utf-8"))
            return

        elif path in ("/api/pause_total", "/pause_total"):
            total_pause = data.get("total_pause", True)
            VOICE_SETTINGS["enabled"] = not total_pause
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "total_pause": total_pause,
                "enabled": VOICE_SETTINGS["enabled"]
            }).encode("utf-8"))
            return

        elif path in ("/api/stop", "/stop"):
            self._set_headers(200)
            self.wfile.write(b'{"status": "stopped"}')
            return

        elif path in ("/api/dostuff_break", "/dostuff_break"):
            task_title = data.get("title", "Take a 60 second movement break").strip()
            mins = data.get("minutes", 5)
            spoken = f"DoStuff {mins} minute reset. {task_title}."
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            audio_url = f"/api/tts?text={urllib.parse.quote(spoken)}&voice={urllib.parse.quote(voice)}"
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "announced",
                "spoken": spoken,
                "audio_url": audio_url
            }).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):
        return
