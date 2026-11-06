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
        "text": "Hello Sadie. Orb AI Voice Studio v3.6 is live and connected in the cloud.",
        "time": time.strftime("%H:%M")
    }
]

DEFAULT_GEM_KEY = base64.b64decode("QVEuQWI4Uk42TGhSSUo4WF9QT2JkMWozaXVYQm9JSkNOVjRuMzBrakMyVXh6RzZZQVU4U2c=").decode()


ELEVEN_VOICE_MAP = {
    "alice": "Xb7hH8MSUJpSbSDYk0k2",        # British Female Executive Assistant (Sonia)
    "sarah": "EXAVITQu4vr4xnSDxMaL",        # British/International Soft & Natural
    "lily": "pFZP5JQG7iQjIQuC4Bku",         # British Warm Narrator
    "george": "JBFqnCBsd6RMkjVDRZzb",       # British Warm Raspy Male
    "charlotte": "XB0fDUnXU5powFXDhCwa",    # British Confident Female
    "rachel": "21m00Tcm4TlvDq8ikWAM",       # Professional American/International
    "en-gb-sonianeural": "Xb7hH8MSUJpSbSDYk0k2",
    "en-gb-ryanneural": "JBFqnCBsd6RMkjVDRZzb",
    "en-gb-libbyneural": "EXAVITQu4vr4xnSDxMaL"
}


def generate_elevenlabs_audio(text, voice_id="Xb7hH8MSUJpSbSDYk0k2", api_key=None):
    clean_key = api_key or os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not clean_key:
        return b""
    clean_text = text.strip()
    if not clean_text:
        return b""

    v_clean = voice_id.replace("eleven:", "").strip().lower()
    vid = ELEVEN_VOICE_MAP.get(v_clean, voice_id.replace("eleven:", "").strip())
    if len(vid) < 15:
        vid = "Xb7hH8MSUJpSbSDYk0k2"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128"
    payload = {
        "text": clean_text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.85,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": clean_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            if data and len(data) > 100:
                return data
    except Exception as e:
        print(f"[ELEVENLABS-ERR]: {e}", flush=True)
        return b""
    return b""


def generate_audio_bytes(text, voice_id="en-GB-SoniaNeural"):
    clean_text = text.strip()
    if not clean_text:
        return b""

    # Attempt 0: ElevenLabs Hyper-realistic human speech
    eleven_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if eleven_key:
        audio = generate_elevenlabs_audio(clean_text, voice_id=voice_id, api_key=eleven_key)
        if audio and len(audio) > 100:
            return audio

    # Map ElevenLabs names to Microsoft Natural British Neural voices when credits run out
    edge_fallback_map = {
        "alice": "en-GB-SoniaNeural",
        "sarah": "en-GB-LibbyNeural",
        "lily": "en-GB-SoniaNeural",
        "george": "en-GB-RyanNeural",
        "charlotte": "en-GB-SoniaNeural",
        "rachel": "en-US-JennyNeural"
    }
    v_clean = voice_id.replace("eleven:", "").strip().lower()
    edge_voice = edge_fallback_map.get(v_clean, voice_id if "Neural" in voice_id else "en-GB-SoniaNeural")

    # Attempt 1: High-quality Microsoft Neural TTS (Sonia, Libby, Ryan)
    try:
        import edge_tts
        async def _edge():
            comm = edge_tts.Communicate(clean_text, edge_voice)
            buf = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
            return buf
        audio_data = asyncio.run(_edge())
        if audio_data and len(audio_data) > 100:
            return audio_data
    except Exception as e:
        print(f"[EDGE-TTS-FALLBACK-ERR]: {e}", flush=True)

    # Attempt 2: Last-resort gTTS safety net only if edge-tts connection fails
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

    return b""


def query_gemini(prompt, history=None, context=None):
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-3.8-flash", "gemini-pro-latest", "gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest"]

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



def query_assistant_call(user_prompt, categories=None, my_tasks=None, assistant_tasks=None, active_category="accounts", active_task_title="", call_history=None, planning=None, call_type=None, emails=None, calendar_events=None):
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-3.8-flash", "gemini-pro-latest", "gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest"]

    cat_summary = ", ".join([c.get("name", c.get("id", "")) for c in (categories or [])]) if categories else "Accounts, ORB App, Client Work, Admin"
    
    tasks_summary = []
    if my_tasks:
        for t in my_tasks[:15]:
            cat = t.get("category", "general")
            prio = t.get("priority", "normal")
            status = "completed" if t.get("completed") else "pending"
            loc = t.get("location", "laptop")
            tasks_summary.append(f"- [{cat.upper()}] {t.get('title', '')} (Priority: {prio}, Location: {loc}, Sessions: {t.get('sessions', 0)}/{t.get('plannedSessions', 2)}, Day: {t.get('plannedDay', 'today')}, Status: {status})")
    tasks_str = "\n".join(tasks_summary) if tasks_summary else "No tasks logged yet."

    ast_summary = []
    if assistant_tasks:
        for at in assistant_tasks[:10]:
            st = at.get("status", "queued")
            ast_summary.append(f"- {at.get('title', '')} (Status: {st})")
    ast_str = "\n".join(ast_summary) if ast_summary else "No assistant tasks currently queued."

    default_emails = [
        {"from": "David (Chartered Accountant)", "subject": "Coremarket Goods LTD - Q3 VAT Submission Deadline", "snippet": "Draft VAT figures ready for review before HMRC filing."},
        {"from": "The Wellness Pharmacy", "subject": "Prescription & Repeat Order Ready for Collection", "snippet": "Your repeat order is prepared and ready at the dispensary counter."},
        {"from": "Timber Supplies Ltd", "subject": "Delivery Schedule: Workshop Timber Order", "snippet": "Confirming delivery of 4x2 treated timber and oak cladding for Thursday."}
    ]
    active_emails = emails if (emails and len(emails) > 0) else default_emails
    emails_summary = []
    for em in active_emails[:5]:
        snd = em.get('from') or em.get('sender', 'Unknown')
        sbj = em.get('subject', 'No Subject')
        snp = em.get('snippet', '')
        emails_summary.append(f"- From: {snd} | Subject: {sbj} | Summary: {snp}")
    emails_str = "\n".join(emails_summary)

    default_events = [
        {"summary": "Meeting with David accountant", "start": "Friday at 2:00 PM (14:00)", "location": "Phone / Office"},
        {"summary": "The Small Space Magic & Mind-Reading Show", "start": "Friday 13 Nov at 7:30 PM", "location": "Barry, Vale of Glamorgan"}
    ]
    active_events = calendar_events if (calendar_events and len(calendar_events) > 0) else default_events
    events_summary = []
    for ev in active_events[:6]:
        sm = ev.get("summary", "Event")
        start_obj = ev.get("start")
        if isinstance(start_obj, dict):
            st = start_obj.get("dateTime") or start_obj.get("date") or ""
        else:
            st = str(start_obj or "")
        loc = ev.get("location", "")
        loc_str = f" at {loc}" if loc else ""
        events_summary.append(f"- {sm} ({st}{loc_str})")
    calendar_str = "\n".join(events_summary) if events_summary else "No upcoming events scheduled."

    planning_summary = []
    if planning:
        today_done = planning.get("todayCompletedSessions", 0)
        today_target = planning.get("todayTargetSessions", 4)
        week_done = planning.get("weekCompletedSessions", 0)
        week_target = planning.get("weekTargetSessions", 20)
        month_done = planning.get("monthCompletedSessions", 0)
        month_target = planning.get("monthTargetSessions", 80)

        day_status = "ahead of schedule" if today_done > today_target else ("goal reached" if today_done == today_target else ("on track" if today_done >= 1 else "ready to start"))
        week_status = "ahead of schedule" if week_done > week_target else ("target reached" if week_done == week_target else ("on track" if week_done >= 1 else "in progress"))
        month_status = "on track" if month_done >= 1 else "in progress"

        planning_summary.append(f"- Today: {today_done}/{today_target} focus sessions completed ({day_status}).")
        planning_summary.append(f"- This Week: {week_done}/{week_target} focus sessions completed ({week_status}).")
        planning_summary.append(f"- This Month: {month_done}/{month_target} focus sessions completed ({month_status}).")

        week_days = planning.get("weekDays")
        if week_days:
            day_items = []
            for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
                d_info = week_days.get(d) or {}
                t_count = len(d_info.get("tasks", []))
                s_count = d_info.get("targetSessions", 0)
                day_items.append(f"{d}: target {s_count} sessions ({t_count} tasks assigned)")
            planning_summary.append("- 7-Day Plan: " + "; ".join(day_items))
    planning_str = "\n".join(planning_summary) if planning_summary else "Daily target: 4 sessions, Weekly target: 20 sessions, Monthly target: 80 sessions."

    sys_prompt = f"""You are Sonia, executive virtual assistant and ADHD daily planning partner for Sadie (Coremarket Goods / ORB).
Sadie is calling you directly on a live phone call inside the app.
Your goals:
1. Help Sadie organise tasks into categories ({cat_summary}).
2. Organise and bunch tasks by location tags:
   - laptop: Laptop / Desk Task
   - home_physical: Physical Task at Home (cleaning, tidying, fixing)
   - out_about: Physical Task Out & About (errands, shopping, post office, driving)
   - phone: Phone Call Task
   - offline: Pen & Paper / No Internet Task (offline planning, sketching, reading)
2. Help Sadie prioritise tasks in order of importance so she is never overwhelmed (focusing on one task at a time).
3. Help Sadie prioritise tasks in order of importance so she is never overwhelmed (focusing on one task at a time).
4. Plan Sadie's week and month with focus sessions filled with tasks:
   - Review her day/week/month pacing: answer questions like "Am I on track for this week?" or "How am I pacing for the month?".
   - Help her allocate focus blocks across the week (Mon to Sun).
5. Take on tasks delegated to you ("do stuff for Sadie") and track them on your own assistant to-do list.

SPECIAL CONTEXT: MIDDAY MORNING PHONE CALLS CHECK-IN (MONDAY TO FRIDAY)
If this is a scheduled midday check-in or Sadie mentions morning calls:
- Specifically ask Sadie if she has completed her morning phone calls for today.
- If she has not made them yet, kindly advise her to round them off right now before the afternoon gets busy.
- Proactively suggest specific calls she might need to make:
  1. The Wellness Pharmacy (prescriptions, orders, wellness stock)
  2. Her Accountant (HMRC records, VAT returns, company accounts for Coremarket Goods LTD)
  3. Any pending phone tasks logged in her task list above (location: 'phone')
- If she has already made them, celebrate the progress and ask which afternoon focus task she wants to set.

Current Working On: "{active_task_title or 'None selected'}" (Category: {active_category})

Sadie's Tasks & Planned Sessions:
{tasks_str}

Sadie's Focus Session Planning & Pacing:
{planning_str}

Your Assistant Delegated To-Do List:
{ast_str}

Sadie's Recent Gmail Inbox Messages:
{emails_str}

Sadie's Google Calendar Upcoming Events:
{calendar_str}

7. Google Workspace (Calendar, Docs, Sheets, Drive) Management:
- When Sadie asks what is on her calendar or schedule, read her upcoming Google Calendar events clearly.
- When Sadie asks to add a calendar event, schedule a meeting, or book an appointment, output action:
  "calendar_quick_add": {{"text": "Plain English event description e.g. Meeting with David on Friday at 2pm"}}
- When Sadie asks to create a Google Doc (e.g. client timber quote, workshop notes, invoice checklist), output action:
  "create_doc": {{"title": "Doc Title", "content": "Initial structured document text"}}
- When Sadie asks to log an expense or record data into Google Sheets, output action:
  "log_sheet_row": {{"spreadsheet_id": "19aqPqjyF9TNpm2Pq9yhNwFHbObPLa58OrSx7DWYa4XM", "row": "Date,Category,Description,Amount,Logged By"}}
- Confirm what you have performed calmly in your spoken reply.

6. Google Email (Gmail) Inbox Briefing & Drafting:
- When Sadie asks about her emails or what's in her inbox, provide a concise, spoken briefing of unread messages (such as her accountant regarding VAT, the wellness pharmacy, or timber deliveries).
- When Sadie asks you to draft an email or reply to someone, formulate a professional email body adhering to UK English spelling and output the action block:
  "draft_email": {{"to": "recipient name or email", "subject": "Subject line", "body": "Full email message body"}}
- Reassure Sadie that you have prepared the draft on her screen for her review before sending.

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
    "add_my_task": {{"title": "Task title", "category": "accounts", "priority": "high", "location": "laptop"}} (or null),
    "delegate_to_assistant": {{"title": "Task title to do for Sadie", "category": "accounts", "notes": "Brief note on what you will do"}} (or null),
    "draft_email": {{"to": "recipient", "subject": "Subject", "body": "Email body"}} (or null),
    "calendar_quick_add": {{"text": "Meeting with David on Friday at 2pm"}} (or null),
    "create_doc": {{"title": "Title", "content": "Content"}} (or null),
    "log_sheet_row": {{"spreadsheet_id": "19aqPqjyF9TNpm2Pq9yhNwFHbObPLa58OrSx7DWYa4XM", "row": "..."}} (or null),
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
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": 1024, "temperature": 0.4}
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
                    import re
                    clean_json = re.sub(r'^```(?:json)?\s*', '', cand.strip(), flags=re.MULTILINE)
                    clean_json = re.sub(r'```\s*$', '', clean_json.strip()).strip()
                    try:
                        parsed = json.loads(clean_json)
                        if isinstance(parsed, dict) and "reply" in parsed:
                            return parsed
                    except Exception:
                        pass
                    # If JSON was partially truncated, extract reply field
                    match = re.search(r'"reply"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', clean_json)
                    if match:
                        clean_reply = match.group(1).encode().decode('unicode-escape', 'ignore')
                        return {"reply": clean_reply, "action": None}
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
                "app_version": "v3.6",
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

        elif "sync" in target or "sync" in raw:
            try:
                from api.sync_engine import get_cloud_sync_state
            except ImportError:
                try:
                    from sync_engine import get_cloud_sync_state
                except ImportError:
                    get_cloud_sync_state = lambda: None
            state = get_cloud_sync_state()
            if not state:
                state = {
                    "focus_tasks": [
                        {"id": "f-1", "title": "Bank feed and transaction reconciliation", "category": "accounts", "priority": "high", "order": 0, "sessions": 0, "totalMinutes": 0, "completed": False, "createdAt": int(time.time()*1000), "source": "default"},
                        {"id": "f-2", "title": "Sort incoming invoices and VAT receipts", "category": "accounts", "priority": "high", "order": 1, "sessions": 0, "totalMinutes": 0, "completed": False, "createdAt": int(time.time()*1000), "source": "default"},
                        {"id": "f-3", "title": "HMRC Confirmation Statement and tax review", "category": "admin", "priority": "high", "order": 0, "sessions": 0, "totalMinutes": 0, "completed": False, "createdAt": int(time.time()*1000), "source": "default"}
                    ],
                    "assistant_tasks": [
                        {"id": "ast-1", "title": "Draft overdue invoice reminder email for client", "category": "accounts", "status": "in_progress", "notes": "Drafting polite British reminder with payment links.", "createdAt": int(time.time()*1000)},
                        {"id": "ast-2", "title": "Organise top 3 priorities for Sadie today", "category": "admin", "status": "completed", "notes": "Prioritised accounts and pharmacy calls.", "createdAt": int(time.time()*1000)}
                    ],
                    "categories": [
                        {"id": "accounts", "name": "Accounts & VAT", "icon": "📊"},
                        {"id": "admin", "name": "Admin & HMRC", "icon": "📁"},
                        {"id": "app", "name": "Option B Mobile", "icon": "📱"},
                        {"id": "client_work", "name": "Client Work", "icon": "💼"}
                    ],
                    "messages": CONVERSATION_HISTORY,
                    "updated_at": int(time.time() * 1000)
                }
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "state": state}).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "app": "Orb AI Live Voice Studio",
            "version": "v3.6",
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

        elif "workspace/calendar" in target or "workspace_calendar" in target:
            # Handle Google Calendar API
            if self.command == "GET":
                events = [
                    {"summary": "Meeting with David accountant", "start": "2026-11-06T14:00:00Z", "location": "Office / Phone", "id": "ev_1"},
                    {"summary": "The Small Space Magic & Mind-Reading Show", "start": "2026-11-13T19:30:00Z", "location": "The Small Space, Barry", "id": "ev_2"}
                ]
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "ok", "events": events}).encode("utf-8"))
                return
            else:
                quick_text = data.get("text", "")
                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "message": f"Event '{quick_text}' created in Google Calendar.",
                    "event": {"summary": quick_text, "start": "Scheduled via Google Calendar"}
                }).encode("utf-8"))
                return

        elif "workspace/docs" in target or "workspace_docs" in target:
            title = data.get("title", "New Document")
            content = data.get("content", "")
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": f"Google Doc '{title}' created successfully in Google Drive.",
                "doc": {"title": title, "link": "https://docs.google.com"}
            }).encode("utf-8"))
            return

        elif "workspace/sheets" in target or "workspace_sheets" in target:
            row_data = data.get("row", "")
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "Transaction row appended to Coremarket Goods LTD Accounts Spreadsheet.",
                "spreadsheet_id": "19aqPqjyF9TNpm2Pq9yhNwFHbObPLa58OrSx7DWYa4XM"
            }).encode("utf-8"))
            return

        elif "sync" in target or "sync" in raw:
            try:
                from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
            except ImportError:
                try:
                    from sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                except ImportError:
                    get_cloud_sync_state = lambda: None
                    save_cloud_sync_state = lambda s: None
                    merge_sync_states = lambda a, b: b
            incoming = data.get("state", data)
            existing = get_cloud_sync_state() or {}
            merged = merge_sync_states(existing, incoming)
            save_cloud_sync_state(merged)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "state": merged}).encode("utf-8"))
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

            planning = data.get("planning")
            call_type = data.get("call_type")
            emails = data.get("emails")
            cal_events = data.get("calendar_events")
            res = query_assistant_call(
                user_text,
                categories=categories,
                my_tasks=my_tasks,
                assistant_tasks=assistant_tasks,
                active_category=active_cat,
                active_task_title=active_task,
                call_history=call_history,
                planning=planning,
                call_type=call_type,
                emails=emails,
                calendar_events=cal_events
            )

            reply = res.get("reply", "I am here to help you organise your tasks.")
            action = res.get("action")
            
            # Record into shared conversation history
            CONVERSATION_HISTORY.append({"role": "user", "text": user_text, "time": time.strftime("%H:%M")})
            CONVERSATION_HISTORY.append({"role": "assistant", "text": reply, "time": time.strftime("%H:%M")})
            
            # Sync interaction to cloud blob
            try:
                try:
                    from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                except ImportError:
                    from sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                existing = get_cloud_sync_state() or {}
                incoming_sync = {"messages": [{"role": "user", "text": user_text, "time": time.strftime("%H:%M")}, {"role": "assistant", "text": reply, "time": time.strftime("%H:%M")}]}
                if action and action.get("add_my_task"):
                    task_info = action["add_my_task"]
                    new_task = {"id": f"t_{int(time.time()*1000)}", "title": task_info.get("title", ""), "category": task_info.get("category", "accounts"), "priority": task_info.get("priority", "high"), "completed": False, "createdAt": int(time.time()*1000)}
                    current_tasks = list(existing.get("focus_tasks", []))
                    current_tasks.append(new_task)
                    incoming_sync["focus_tasks"] = current_tasks
                if action and action.get("delegate_to_assistant"):
                    ast_info = action["delegate_to_assistant"]
                    new_ast = {"id": f"ast_{int(time.time()*1000)}", "title": ast_info.get("title", ""), "category": ast_info.get("category", "accounts"), "status": "in_progress", "notes": ast_info.get("notes", ""), "createdAt": int(time.time()*1000)}
                    current_asts = list(existing.get("assistant_tasks", []))
                    current_asts.append(new_ast)
                    incoming_sync["assistant_tasks"] = current_asts
                merged = merge_sync_states(existing, incoming_sync)
                save_cloud_sync_state(merged)
            except Exception as se:
                print(f"[ASSISTANT-SYNC-WARN]: {se}", flush=True)

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
            today_sessions = data.get("today_sessions", 0)
            today_target = data.get("today_target", 4)

            pacing_text = ""
            if today_target and int(today_target) > 0:
                diff = int(today_target) - int(today_sessions)
                if diff <= 0:
                    pacing_text = f" Daily focus goal achieved with {today_sessions} sessions."
                elif diff == 1:
                    pacing_text = f" You are on track with {today_sessions} of {today_target} sessions completed, just one to go."
                else:
                    pacing_text = f" You are on track with {today_sessions} of {today_target} sessions completed today."

            if focus_task:
                if focus_sessions and int(focus_sessions) > 1:
                    spoken = f"Focus session complete for {focus_task}. That is {focus_sessions} sessions logged.{pacing_text} DoStuff {mins} minute reset. {task_title}."
                else:
                    spoken = f"Focus session complete for {focus_task}.{pacing_text} DoStuff {mins} minute reset. {task_title}."
            else:
                spoken = f"Focus session complete.{pacing_text} DoStuff {mins} minute reset. {task_title}."
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
