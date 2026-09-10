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
    "silence_timeout": 1.2
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
        
        if path in ("/", "/index.html"):
            html_file = os.path.join(base_dir, "web_app", "index.html")
            if os.path.exists(html_file):
                with open(html_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content.encode("utf-8"))
                return
        elif path == "/manifest.json":
            m_file = os.path.join(base_dir, "web_app", "manifest.json")
            if os.path.exists(m_file):
                with open(m_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "application/manifest+json")
                self.wfile.write(content.encode("utf-8"))
                return
        elif path == "/sw.js":
            s_file = os.path.join(base_dir, "web_app", "sw.js")
            if os.path.exists(s_file):
                with open(s_file, "r", encoding="utf-8") as f:
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
        if path == "/api/settings":
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
