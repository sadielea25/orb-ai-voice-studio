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
        "text": "Hello Sadie. Orb AI Voice Studio v3.3 is live and connected in the cloud.",
        "time": time.strftime("%H:%M")
    }
]

DEFAULT_GEM_KEY = base64.b64decode("QVEuQWI4Uk42TGhSSUo4WF9QT2JkMWozaXVYQm9JSkNOVjRuMzBrakMyVXh6RzZZQVU4U2c=").decode()


def generate_audio_bytes(text, voice_id="en-GB-SoniaNeural"):
    clean_text = text.strip()
    if not clean_text:
        return b""

    # Attempt 1: High-reliability Google TTS (gTTS) - 100% reliable on cloud datacenter IPs
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
        data = fp.getvalue()
        if data and len(data) > 100:
            return data
    except Exception:
        pass

    # Attempt 2: Edge-TTS
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

    return b""


def query_gemini(prompt, history=None, context=None):
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]

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



def query_assistant_call(user_prompt, categories=None, my_tasks=None, assistant_tasks=None, active_category="accounts", active_task_title="", call_history=None):
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]

    cat_summary = ", ".join([c.get("name", c.get("id", "")) for c in (categories or [])]) if categories else "Accounts, ORB App, Client Work, Admin"
    
    tasks_summary = []
    if my_tasks:
        for t in my_tasks[:15]:
            cat = t.get("category", "general")
            prio = t.get("priority", "normal")
            status = "completed" if t.get("completed") else "pending"
            tasks_summary.append(f"- [{cat.upper()}] {t.get('title', '')} (Priority: {prio}, Status: {status})")
    tasks_str = "\n".join(tasks_summary) if tasks_summary else "No tasks logged yet."

    ast_summary = []
    if assistant_tasks:
        for at in assistant_tasks[:10]:
            st = at.get("status", "queued")
            ast_summary.append(f"- {at.get('title', '')} (Status: {st})")
    ast_str = "\n".join(ast_summary) if ast_summary else "No assistant tasks currently queued."

    sys_prompt = f"""You are Sonia, executive virtual assistant and ADHD daily planning partner for Sadie (Coremarket Goods / ORB).
Sadie is calling you directly on a live phone call inside the app.
Your goals:
1. Help Sadie organise tasks into categories ({cat_summary}).
2. Help Sadie prioritise tasks in order of importance so she is never overwhelmed (focusing on one task at a time).
3. Plan Sadie's priority tasks for the day.
4. Take on tasks delegated to you ("do stuff for Sadie") and track them on your own assistant to-do list.

Current Working On: "{active_task_title or 'None selected'}" (Category: {active_category})

Sadie's Tasks:
{tasks_str}

Your Assistant Delegated To-Do List:
{ast_str}

CRITICAL RULES:
- Tone: Warm, calm, confident, articulate British executive assistant.
- Strictly adhere to UK English spelling (prioritise, categorise, organise) and vocabulary.
- NEVER USE EXCLAMATION MARKS. End sentences with a standard full stop.
- Keep spoken replies concise (2-3 natural sentences suitable for spoken voice audio).

Format your output as valid JSON:
{{
  "reply": "Your warm spoken reply to Sadie",
  "action": {{
    "set_focus_task_title": "Task title to set as active Working On (or null)",
    "add_my_task": {{"title": "Task title", "category": "accounts", "priority": "high"}} (or null),
    "delegate_to_assistant": {{"title": "Task title to do for Sadie", "category": "accounts", "notes": "Brief note on what you will do"}} (or null),
    "reordered_priorities": [{{"id": "...", "priority": "high"}}] (or null)
  }}
}}
If no action is triggered, leave action fields null or omit them. Return ONLY valid JSON."""

    contents = []
    if call_history:
        for msg in call_history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            txt = msg.get("text", "").strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt}]})
    contents.append({"role": "user", "parts": [{"text": user_prompt}]})

    payload = {
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": 512, "temperature": 0.5}
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
            with urllib.request.urlopen(req, timeout=8) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                cand = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if cand:
                    cand = cand.replace("!", ".")
                    try:
                        return json.loads(cand)
                    except Exception:
                        return {"reply": cand, "action": None}
        except Exception:
            continue

    return {
        "reply": f"I am right here with you Sadie. Let us look at your top priority task under {active_category} and take it one step at a time.",
        "action": None
    }

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

    def resolve_target(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        matched = self.headers.get("x-matched-path", "")
        subpath = q.get("__path", [""])[0]
        
        target = parsed.path
        if subpath:
            target = "/" + subpath.lstrip("/")
        elif matched:
            target = matched.split("?")[0]
        return target.lower(), q

    def do_GET(self):
        target, q = self.resolve_target()
        raw = self.path.lower()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        api_dir = os.path.dirname(os.path.abspath(__file__))

        if target in ("/", "/index.html") and "status" not in raw and "tts" not in raw and "settings" not in raw:
            for candidate in [
                os.path.join(base_dir, "public", "index.html"),
                os.path.join(base_dir, "web_app", "index.html"),
                os.path.join(api_dir, "index.html")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "text/html; charset=utf-8")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif "manifest.json" in target or "manifest.json" in raw:
            for candidate in [
                os.path.join(base_dir, "public", "manifest.json"),
                os.path.join(base_dir, "web_app", "manifest.json")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/manifest+json")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif "sw.js" in target or "sw.js" in raw:
            for candidate in [
                os.path.join(base_dir, "public", "sw.js"),
                os.path.join(base_dir, "web_app", "sw.js")
            ]:
                if os.path.exists(candidate):
                    with open(candidate, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._set_headers(200, "application/javascript")
                    self.wfile.write(content.encode("utf-8"))
                    return

        elif "status" in target or "status" in raw:
            state = {
                "status": "online",
                "mode": "cloud",
                "app_version": "v3.3",
                "active_chat_title": "Orb AI Cloud Studio",
                "is_speaking": False,
                "enabled": VOICE_SETTINGS.get("enabled", True),
                "voice": VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(state).encode("utf-8"))
            return

        elif "voice_preview" in target or "voice_preview" in raw:
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

        elif "tts" in target or "tts" in raw:
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

        elif "settings" in target or "settings" in raw:
            self._set_headers(200)
            self.wfile.write(json.dumps(VOICE_SETTINGS).encode("utf-8"))
            return

        elif "conversation" in target or "conversation" in raw:
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": CONVERSATION_HISTORY}).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "app": "Orb AI Live Voice Studio",
            "version": "v3.3",
            "status": "online",
            "cloud": True
        }).encode("utf-8"))

    def do_POST(self):
        target, q = self.resolve_target()
        raw = self.path.lower()

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if "speech_input" in target or "speech_input" in raw:
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

        elif "read_ai_reply" in target or "speak_last" in target or "read_ai_reply" in raw or "speak_last" in raw:
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

        elif "polish" in target or "polish" in raw:
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

        elif "settings" in target or "settings" in raw:
            VOICE_SETTINGS.update(data)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "saved", "settings": VOICE_SETTINGS}).encode("utf-8"))
            return

        elif "pause_total" in target or "pause_total" in raw:
            total_pause = data.get("total_pause", True)
            VOICE_SETTINGS["enabled"] = not total_pause
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "total_pause": total_pause,
                "enabled": VOICE_SETTINGS["enabled"]
            }).encode("utf-8"))
            return

        elif "stop" in target or "stop" in raw:
            self._set_headers(200)
            self.wfile.write(b'{"status": "stopped"}')
            return

        elif "assistant_call" in target or "assistant_call" in raw:
            user_text = data.get("text", "").strip()
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            categories = data.get("categories", [])
            my_tasks = data.get("my_tasks", [])
            assistant_tasks = data.get("assistant_tasks", [])
            active_cat = data.get("active_category", "accounts")
            active_task = data.get("active_task_title", "")
            call_history = data.get("call_history", [])

            if not user_text:
                user_text = "Hello Sonia, help me organise and plan my priority tasks for today."

            res = query_assistant_call(
                user_text,
                categories=categories,
                my_tasks=my_tasks,
                assistant_tasks=assistant_tasks,
                active_category=active_cat,
                active_task_title=active_task,
                call_history=call_history
            )

            reply = res.get("reply", "I am here to help you organise your tasks.")
            action = res.get("action")
            audio_url = f"/api/tts?text={urllib.parse.quote(reply)}&voice={urllib.parse.quote(voice)}"
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "reply": reply,
                "action": action,
                "audio_url": audio_url
            }).encode("utf-8"))
            return

        elif "dostuff_break" in target or "dostuff_break" in raw:
            task_title = data.get("title", "Take a 60 second movement break").strip()
            mins = data.get("minutes", 5)
            focus_task = data.get("focus_task", "").strip()
            focus_sessions = data.get("focus_sessions", 0)
            if focus_task:
                if focus_sessions and int(focus_sessions) > 1:
                    spoken = f"Focus session complete for {focus_task}. That is {focus_sessions} sessions logged. DoStuff {mins} minute reset. {task_title}."
                else:
                    spoken = f"Focus session complete for {focus_task}. DoStuff {mins} minute reset. {task_title}."
            else:
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
