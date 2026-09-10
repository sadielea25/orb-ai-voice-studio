"""
bridge_server.py
Lightweight HTTP Bridge Server connecting the AI Chat to the Chrome Extension.
Listens on http://127.0.0.1:8765
"""

import sys
import os
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_state.json")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"action": "none", "params": {}, "last_report": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


class BridgeHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        if self.path == "/command":
            state = load_state()
            self._set_headers(200)
            self.wfile.write(json.dumps(state).encode("utf-8"))
            if state.get("action") != "none":
                state["action"] = "none"
                save_state(state)
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

        if self.path == "/report":
            state = load_state()
            state["last_report"] = data
            save_state(state)
            self._set_headers(200)
            self.wfile.write(b'{"status": "ok"}')
        elif self.path == "/send":
            state = load_state()
            state["action"] = data.get("action", "none")
            state["params"] = data.get("params", {})
            save_state(state)
            self._set_headers(200)
            self.wfile.write(b'{"status": "queued"}')
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')

    def log_message(self, format, *args):
        return


def run_server(port=8765):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, BridgeHandler)
    print(f"AI Bridge Server running on http://127.0.0.1:{port}", flush=True)
    httpd.serve_forever()


def queue_command(action, params):
    state = load_state()
    state["action"] = action
    state["params"] = params
    save_state(state)
    print(f"Command '{action}' queued for Chrome Extension!", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Chrome Extension Bridge")
    parser.add_argument("command", choices=["server", "send", "status", "speak", "validate"], default="server", nargs="?")
    parser.add_argument("--action", default="fill_aa02")
    parser.add_argument("--text", default="Hello! I am speaking through your speakers.")
    parser.add_argument("--unpaid", default="1")
    parser.add_argument("--cash", default="0")
    parser.add_argument("--shares", default="1")
    parser.add_argument("--class", dest="share_class", default="Ordinary")
    parser.add_argument("--value", default="1")
    parser.add_argument("--date", default=None)

    args = parser.parse_args()

    if args.command == "server":
        run_server()
    elif args.command == "speak":
        queue_command("speak", {"text": args.text})
    elif args.command == "validate":
        queue_command("click_validate", {})
    elif args.command == "send":
        queue_command(args.action, {
            "text": args.text,
            "unpaid": args.unpaid,
            "cash": args.cash,
            "shares": args.shares,
            "share_class": args.share_class,
            "value": args.value,
            "date": args.date
        })
    elif args.command == "status":
        state = load_state()
        print("Current State:", json.dumps(state, indent=2), flush=True)
