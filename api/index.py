"""
api/index.py
Vercel Serverless Function for Orb AI Live Voice Studio Cloud API.
"""

from http.server import BaseHTTPRequestHandler
import os
import json
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
        "text": "Hello Sadie! Orb AI Voice Studio v1.0 is live and connected.",
        "time": "15:45"
    }
]


class handler(BaseHTTPRequestHandler):
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
        path = self.path.split("?")[0]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        api_dir = os.path.dirname(os.path.abspath(__file__))
        
        if path in ("/", "/index.html"):
            for candidate in [
                os.path.join(api_dir, "index.html"),
                os.path.join(base_dir, "public", "index.html"),
                os.path.join(base_dir, "web_app", "index.html"),
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
                os.path.join(api_dir, "manifest.json"),
                os.path.join(base_dir, "public", "manifest.json"),
                os.path.join(base_dir, "web_app", "manifest.json")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/manifest+json")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif path == "/sw.js":
            for candidate in [
                os.path.join(api_dir, "sw.js"),
                os.path.join(base_dir, "public", "sw.js"),
                os.path.join(base_dir, "web_app", "sw.js")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/javascript")
                    self.wfile.write(content.encode("utf-8"))
                    return
        elif path == "/api/settings":
            self._set_headers(200)
            self.wfile.write(json.dumps(VOICE_SETTINGS).encode("utf-8"))
            return
        elif path == "/api/status":
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "online", "mode": "cloud-v1.0"}).encode("utf-8"))
            return
        elif path == "/api/conversation":
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": CONVERSATION_HISTORY}).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "app": "Orb AI Live Voice Studio",
            "version": "1.0.0",
            "status": "active"
        }).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        path = self.path.split("?")[0]
        if path == "/api/polish_text":
            raw_text = data.get("text", "").strip()
            if not raw_text:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ok", "polished": ""}')
                return

            api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyDRqJUd_G-_JW2pmM48Rs7qi61c48k7Tx4")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
            payload = {
                "system_instruction": {
                    "parts": [{"text": "You are an AI Speech Polishing Engine (TextBlaze / Grammarly style). Your job is to take raw spoken voice-to-text and output a clean, polished, grammatically sound version. Fix accent slips, repeated phrases, misheard words, and awkward phrasing while strictly preserving the speaker's original intent, personality, and tone. Return ONLY the polished plain text sentences with no quotation marks, no markdown formatting, and no commentary."}]
                },
                "contents": [{"parts": [{"text": raw_text}]}]
            }

            polished = raw_text
            try:
                import urllib.request
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidate = resp_data.get("candidates", [{}])[0]
                    parts = candidate.get("content", {}).get("parts", [])
                    if parts and parts[0].get("text"):
                        ai_text = parts[0]["text"].strip()
                        if (ai_text.startswith('"') and ai_text.endswith('"')) or (ai_text.startswith("'") and ai_text.endswith("'")):
                            ai_text = ai_text[1:-1].strip()
                        if ai_text:
                            polished = ai_text
            except Exception:
                pass

            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "polished": polished}).encode("utf-8"))
            return

        elif path == "/api/settings":
            VOICE_SETTINGS.update(data)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "saved", "settings": VOICE_SETTINGS}).encode("utf-8"))
        elif path == "/api/speech_input":
            text = data.get("text", "").strip()
            if text:
                CONVERSATION_HISTORY.append({
                    "role": "user",
                    "text": text,
                    "time": time.strftime("%H:%M")
                })
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "received"}).encode("utf-8"))
        elif path == "/api/test":
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "spoken", "cloud": True}).encode("utf-8"))
        else:
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

    def log_message(self, format, *args):
        return
