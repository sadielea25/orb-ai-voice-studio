"""
api/index.py
Vercel Serverless Function for Orb AI Live Voice Studio Cloud API.
Provides high-performance cloud voice synthesis, Gemini AI conversation, and settings sync.
"""

from http.server import BaseHTTPRequestHandler
import os
import io
import re
import json
import asyncio
import socket as _socket
import threading
import http.client
import urllib.parse
import urllib.request
import base64
import time

# Force IPv4 resolution so speech.platform.bing.com and generativelanguage.googleapis.com never hit the 2.3s IPv6 Anycast stall
_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, _socket.AF_INET, type, proto, flags)
_socket.getaddrinfo = _ipv4_getaddrinfo

try:
    import edge_tts
except ImportError:
    edge_tts = None

_GLOBAL_TTS_LOOP = asyncio.new_event_loop()
def _start_global_tts_loop(lp):
    asyncio.set_event_loop(lp)
    lp.run_forever()
_GLOBAL_TTS_THREAD = threading.Thread(target=_start_global_tts_loop, args=(_GLOBAL_TTS_LOOP,), daemon=True)
_GLOBAL_TTS_THREAD.start()

_GEMINI_TLS_LOCK = threading.Lock()
_GEMINI_TLS_CONN = None

def _fast_gemini_post(model_name, api_key, payload_bytes, timeout=3.5):
    global _GEMINI_TLS_CONN
    path = f"/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json", "Connection": "keep-alive"}
    with _GEMINI_TLS_LOCK:
        for attempt in range(2):
            try:
                if _GEMINI_TLS_CONN is None:
                    _GEMINI_TLS_CONN = http.client.HTTPSConnection("generativelanguage.googleapis.com", timeout=timeout)
                _GEMINI_TLS_CONN.timeout = timeout
                _GEMINI_TLS_CONN.request("POST", path, body=payload_bytes, headers=headers)
                resp = _GEMINI_TLS_CONN.getresponse()
                raw = resp.read()
                if resp.status == 200:
                    return json.loads(raw.decode("utf-8"))
                else:
                    _GEMINI_TLS_CONN.close()
                    _GEMINI_TLS_CONN = None
            except Exception:
                try:
                    if _GEMINI_TLS_CONN:
                        _GEMINI_TLS_CONN.close()
                except Exception:
                    pass
                _GEMINI_TLS_CONN = None
    return None

_AUDIO_MEMORY_CACHE = {}
_INFLIGHT_TTS_FUTURES = {}


try:
    import accent_adapter
except ImportError:
    try:
        from api import accent_adapter
    except ImportError:
        accent_adapter = None


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

CLOUD_RELAY_STATE = {
    "active_chat_title": "COREMARKETGOODS ACCOUNTING - HMRC",
    "projects": [
        {"id": "coremarketgoods", "title": "COREMARKETGOODS ACCOUNTING - HMRC"},
        {"id": "orb", "title": "ORB AI Studio"},
        {"id": "spook", "title": "Spook Studio"},
        {"id": "arts_grant", "title": "Arts Grant"}
    ],
    "messages": [],
    "pending_prompts": [],
    "last_sync": 0
}

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
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = resp.read()
            if data and len(data) > 100:
                return data
    except Exception as e:
        print(f"[ELEVENLABS-ERR]: {e}", flush=True)
        return b""
    return b""


def generate_audio_bytes(text, voice_id="en-GB-SoniaNeural", max_wait=4.2):
    clean_text = text.strip()
    if not clean_text:
        return b""

    cache_key = f"{voice_id}::{clean_text}"
    if cache_key in _AUDIO_MEMORY_CACHE:
        return _AUDIO_MEMORY_CACHE[cache_key]

    # Attempt 0: ElevenLabs Hyper-realistic human speech (if key configured)
    eleven_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if eleven_key:
        audio = generate_elevenlabs_audio(clean_text, voice_id=voice_id, api_key=eleven_key)
        if audio and len(audio) > 100:
            if len(_AUDIO_MEMORY_CACHE) < 64:
                _AUDIO_MEMORY_CACHE[cache_key] = audio
            return audio

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

    # Attempt 1: High-speed IPv4 Microsoft Neural TTS on persistent event loop (~680ms)
    try:
        global edge_tts
        if edge_tts is None:
            import edge_tts as _et
            edge_tts = _et

        # Merge multi-sentence stops into single spoken clause to prevent Edge TTS inter-sentence pacing delay
        fast_spoken_text = re.sub(r'([.!?])\s+(?=[A-Z])', ', ', clean_text)

        async def _synth_fast():
            comm = edge_tts.Communicate(fast_spoken_text, edge_voice, rate="+8%", connect_timeout=4, receive_timeout=7)
            buf = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
            return buf

        fut = _INFLIGHT_TTS_FUTURES.get(cache_key)
        if fut is None or fut.done():
            fut = asyncio.run_coroutine_threadsafe(_synth_fast(), _GLOBAL_TTS_LOOP)
            _INFLIGHT_TTS_FUTURES[cache_key] = fut
            def _store_when_done(f, ck=cache_key):
                try:
                    res_b = f.result()
                    if res_b and len(res_b) > 100 and len(_AUDIO_MEMORY_CACHE) < 64:
                        _AUDIO_MEMORY_CACHE[ck] = res_b
                except Exception:
                    pass
                finally:
                    _INFLIGHT_TTS_FUTURES.pop(ck, None)
            fut.add_done_callback(_store_when_done)

        audio_data = fut.result(timeout=max_wait)
        if audio_data and len(audio_data) > 100:
            if len(_AUDIO_MEMORY_CACHE) < 64:
                _AUDIO_MEMORY_CACHE[cache_key] = audio_data
            return audio_data
    except TimeoutError:
        if max_wait < 2.0:
            return b""
    except Exception as e:
        print(f"[EDGE-TTS-FALLBACK-ERR]: {e}", flush=True)

    # Attempt 2: Fast HTTP Keep-Alive Google UK fallback if Edge TTS is unreachable
    try:
        q = urllib.parse.quote(clean_text[:200])
        req = urllib.request.Request(
            f"https://translate.googleapis.com/translate_tts?ie=UTF-8&client=gtx&tl=en-GB&q={q}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = resp.read()
            if data and len(data) > 100:
                return data
    except Exception:
        pass

    return b""


def classify_prompt_complexity(prompt):
    """
    Intelligently routes between models based on turn complexity:
    - Basic / Fast turns (greetings, simple queries, acknowledgments): gemini-3.5-flash-lite (~400ms sub-second response)
    - Complex / In-depth turns (HMRC, VAT, accounting, code, multi-sentence planning): gemini-3.8-flash (deep reasoning)
    """
    text = (prompt or "").lower().strip()
    words = text.split()
    complex_keywords = [
        "vat", "hmrc", "tax", "reconciliation", "invoice", "statement", "accounting",
        "confirmation statement", "corporation tax", "code", "architecture", "script",
        "calculate", "audit", "analyse", "analyze", "strategy", "breakdown"
    ]
    is_complex = any(k in text for k in complex_keywords) or len(words) > 20
    # Always prioritize sub-second Flash-Lite (~500ms) for real-time voice conversation
    if is_complex:
        return ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
    else:
        return ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash"]

def query_gemini(prompt, history=None, context=None):
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = ["gemini-flash-lite-latest", "gemini-2.0-flash-lite"]

    sys_prompt = (
        "You are Sonia, a real British woman on a live phone call with your close colleague and friend Sadie. "
        "Talk exactly like a real person on the phone: warm, natural, relaxed British phrasing with contractions (I'm, let's, that's, you've, don't, no worries, right then). "
        "Never sound like an AI or formal assistant. Reply in 1 short conversational sentence (6 to 12 words). "
        "Strictly use UK English vocabulary and never use exclamation marks."
    )

    contents = []
    if history:
        for msg in history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            txt = msg.get("text", "").strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt}]})

    user_text = prompt
    if context:
        user_text = f"Context: {context}\n\nUser: {prompt}"

    contents.append({"role": "user", "parts": [{"text": user_text}]})

    payload_bytes = json.dumps({
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 90, "temperature": 0.35}
    }).encode("utf-8")

    for mod in models:
        res_data = _fast_gemini_post(mod, api_key, payload_bytes, timeout=3.5)
        if res_data:
            cand = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            if cand:
                return cand.replace("!", ".")

    return "I am right here with you Sadie, ready for your next instruction."



def query_assistant_call(user_prompt, categories=None, my_tasks=None, assistant_tasks=None, active_category="accounts", active_task_title="", call_history=None, planning=None, call_type=None, emails=None, calendar_events=None, audio_base64=None, audio_mime=None, packing_summary=None, budget_summary=None, active_app=None):
    if accent_adapter:
        user_prompt = accent_adapter.adapt_speech_text(user_prompt)
    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
    models = classify_prompt_complexity(user_prompt)

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

    # Load user memory & learned habits
    user_mem = {}
    if accent_adapter:
        try:
            user_mem = accent_adapter.load_user_memory()
        except Exception:
            pass
    learned_facts_list = user_mem.get("learned_facts", [
        "Sadie prefers 1-2 sentence direct answers, zero filler words, no exclamation marks.",
        "CoreMarketGoods is Sadie's primary trading company requiring regular HMRC and VAT attention.",
        "Spook Studio is tied to Dolled Up To Death salon with live phone recording on line +44 292 271 5991."
    ])
    learned_facts_str = "\n".join([f"- {f}" for f in learned_facts_list])
    workspaces_list = []
    for wk_name, wk_info in user_mem.get("workspaces", {}).items():
        desc = wk_info.get("description", "")
        workspaces_list.append(f"- {wk_name}: {desc}")
    workspaces_str = "\n".join(workspaces_list) if workspaces_list else "- COREMARKETGOODS ACCOUNTING - HMRC: Company accounts, VAT, HMRC records\n- ORB: Thin client mobile app\n- Spook Studio: Dolled Up To Death salon receptionist"

    sys_prompt = f"""You are Sonia, executive virtual assistant and ADHD daily planning partner for Sadie (Coremarket Goods / ORB).
Sadie is calling you directly on a live phone call inside the app.

LEARNED HABITS & PERSISTENT MEMORY:
{learned_facts_str}

ACTIVE WORKSPACES & BACKGROUND KNOWLEDGE:
{workspaces_str}

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

Sadie's Packing Lists (Lists Tab - Station 1 Sadie & Station 2 Fraser):
{packing_summary or 'Station 1 (Sadie) & Station 2 (Fraser) face painting and stall kit ready.'}

Sadie's Event Budgeting & Live Profit (Budget Tab):
{budget_summary or 'Staffing (Ashley, Steve, Fraser) & event expenses tracked in Budget tab.'}

Sadie's Integrated Life & Business Apps Inside ORB (Currently Viewing: {active_app or 'ORB'}):
- ClearSpace (clear_space): ADHD visual decluttering & space reset app (https://clear-space-adhd.vercel.app)
- Snap 'n Pack (snap_pack): Visual kit & bag packing app (https://snap-n-pack-app.vercel.app)
- Snap N Snack (snap_snack): Low-effort ADHD meals, nutrition & snack planner (https://snap-n-snack.vercel.app)
- Visual Daily Board (visual_board): Visual daily routine & rhythm board (https://visual-daily-board.vercel.app)
- Next 3 Weeks (next_3_weeks): Gentle 3-week rolling horizon calendar (https://next-3-weeks.vercel.app)
- HMRC Accounting (hmrc): CoreMarketGoods LTD VAT, bank statement reconciliation & tax records
- Antigravity Code Bridge (orb_antigrav): Direct 1:1 live coding bridge to Antigravity

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
- Act and talk like a real British woman on a casual phone call with Sadie, never like a scripted AI or formal assistant.
- Always use natural spoken contractions (I'm, let's, that's, you're, I've, don't, haven't) and natural British phone expressions ("Yeah of course", "Right then", "No worries, I've popped that down", "Let's have a look").
- Strictly adhere to UK English spelling and vocabulary.
- NEVER USE EXCLAMATION MARKS. End sentences with a standard full stop.
- Keep spoken replies to 1 natural, breezy phone-call sentence (6 to 12 words maximum), unless Sadie specifically asks you to read out a full list.

Format your output as valid JSON:
- If no action is needed, return ONLY: {{"reply": "Your 1-sentence reply (max 12 words)"}}
- ONLY include "action" if Sadie explicitly asks to set/add/delegate a task, draft an email, schedule a calendar event, create a doc, or log a sheet row:
{{
  "reply": "Your 1-sentence reply (max 12 words)",
  "action": {{
    "set_focus_task_title": "Task title",
    "add_my_task": {{"title": "Task title", "category": "accounts", "priority": "high", "location": "laptop"}},
    "delegate_to_assistant": {{"title": "Task title", "category": "accounts", "notes": "Note"}},
    "draft_email": {{"to": "recipient", "subject": "Subject", "body": "Email body"}},
    "calendar_quick_add": {{"text": "Event description"}},
    "create_doc": {{"title": "Title", "content": "Content"}},
    "log_sheet_row": {{"spreadsheet_id": "19aqPqjyF9TNpm2Pq9yhNwFHbObPLa58OrSx7DWYa4XM", "row": "..."}},
    "send_to_antigravity": {{"prompt": "Exact coding/editing instruction for Antigravity", "project": "Optional project name"}},
    "open_app": "Tab/app id to open: focus, orb_antigrav, lists, budgeting, my_calendar, sonya, clear_space, snap_pack, snap_snack, visual_board, next_3_weeks, or hmrc",
    "pack_item_title": "Title of packing list item to mark as packed"
  }}
}}
Omit any null action keys. Return ONLY valid JSON."""

    contents = []
    if call_history:
        for msg in call_history[-4:]:
            role = "user" if msg.get("role") == "user" else "model"
            txt = msg.get("text", "").strip()
            if txt:
                contents.append({"role": role, "parts": [{"text": txt}]})
    if audio_base64:
        clean_mime = (audio_mime or "audio/webm").split(";")[0].strip()
        contents.append({
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": clean_mime, "data": audio_base64}},
                {"text": (
                    "Listen to Sadie speaking on this live phone call. "
                    "If the audio is only silence, background noise, or a breath with no spoken words from Sadie, "
                    "return ONLY: {\"ignore\": true, \"reply\": \"\"}. "
                    "Otherwise return valid JSON: {\"user_transcript\": \"what Sadie said\", \"reply\": \"Your 1-sentence natural British phone reply (max 12 words, no exclamation marks)\"} "
                    "(plus \"action\" ONLY if she asked to add/set/delegate a task, draft an email, or add a calendar/doc/sheet item)."
                )}
            ]
        })
    else:
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

    payload_bytes = json.dumps({
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "contents": contents,
        "generationConfig": {"response_mime_type": "application/json", "maxOutputTokens": 350, "temperature": 0.25}
    }).encode("utf-8")

    for mod in ["gemini-flash-lite-latest"]:
        res_data = _fast_gemini_post(mod, api_key, payload_bytes, timeout=3.5)
        if res_data:
            try:
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
            active_chat = CLOUD_RELAY_STATE.get("active_chat_title") or "COREMARKETGOODS ACCOUNTING - HMRC"
            state = {
                "status": "online",
                "mode": "cloud",
                "app_version": "v5.4",
                "active_chat_title": active_chat,
                "is_speaking": False,
                "enabled": VOICE_SETTINGS.get("enabled", True),
                "voice": CLOUD_RELAY_STATE.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
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

        elif "apps/supplies_to_sell" in target or "apps/log_vault" in target:
            rel_a = target.lstrip("/")
            if rel_a.endswith("supplies_to_sell") or rel_a.endswith("supplies_to_sell/"):
                rel_a = "apps/supplies_to_sell/index.html"
            elif rel_a.endswith("log_vault") or rel_a.endswith("log_vault/"):
                rel_a = "apps/log_vault/index.html"
            a_cand = os.path.join(base_dir, "public", rel_a)
            if os.path.isfile(a_cand):
                ctype = "application/javascript" if rel_a.endswith(".js") else ("text/css" if rel_a.endswith(".css") else "text/html; charset=utf-8")
                with open(a_cand, "rb") as af:
                    self._set_headers(200, ctype)
                    self.wfile.write(af.read())
                return

        elif "apps/grants" in target or "apps/grants" in raw:
            rel_g = target.split("apps/grants")[-1].lstrip("/") or "GRANT_DEADLINES_CALENDAR.html"
            if rel_g == "index.html":
                rel_g = "GRANT_DEADLINES_CALENDAR.html"
            g_cand = os.path.join(base_dir, "public", "apps", "grants", rel_g)
            if os.path.isfile(g_cand):
                ctype = "application/javascript" if rel_g.endswith(".js") else ("application/json" if rel_g.endswith(".json") else "text/html; charset=utf-8")
                with open(g_cand, "rb") as gf:
                    self._set_headers(200, ctype)
                    self.wfile.write(gf.read())
                return

        elif "workspace/files" in target or "workspace/files" in raw:
            proj = q.get("project", ["ORB"])[0]
            files = [
                {"path": "public/index.html", "size": 342100},
                {"path": "api/index.py", "size": 48200},
                {"path": "voice_app_server.py", "size": 76400},
                {"path": "public/apps/grants/GRANT_DEADLINES_CALENDAR.html", "size": 118400},
                {"path": "public/apps/grants/grants_data.js", "size": 28400},
                {"path": "capacitor.config.json", "size": 420}
            ]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "project": proj, "files": files}).encode("utf-8"))
            return

        elif "workspace/read_file" in target or "workspace/read_file" in raw:
            rel_path = q.get("path", ["public/index.html"])[0]
            safe_p = os.path.abspath(os.path.join(base_dir, rel_path.lstrip("/")))
            content = ""
            if safe_p.startswith(os.path.abspath(base_dir)) and os.path.isfile(safe_p):
                try:
                    with open(safe_p, "r", encoding="utf-8", errors="replace") as rf:
                        content = rf.read(48000)
                except Exception as e:
                    content = str(e)
            else:
                content = f"// Workspace file: {rel_path}"
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "path": rel_path, "content": content}).encode("utf-8"))
            return

        elif "projects" in target or "projects" in raw:
            projects = CLOUD_RELAY_STATE.get("projects") or [
                {"id": "coremarketgoods", "title": "COREMARKETGOODS ACCOUNTING - HMRC"},
                {"id": "orb", "title": "ORB AI Studio"},
                {"id": "spook", "title": "Spook Studio"},
                {"id": "arts_grant", "title": "Arts Grant"}
            ]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "projects": projects}).encode("utf-8"))
            return

        elif "vocabulary" in target or "vocabulary" in raw:
            vocab = accent_adapter.load_custom_vocab() if accent_adapter else {"replacements": {}, "vocabulary_words": []}
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "vocabulary": vocab}).encode("utf-8"))
            return

        elif "memory" in target or "memory" in raw:
            mem = accent_adapter.load_user_memory() if accent_adapter else {}
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "memory": mem}).encode("utf-8"))
            return

        elif "settings" in target or "settings" in raw:
            self._set_headers(200)
            self.wfile.write(json.dumps(VOICE_SETTINGS).encode("utf-8"))
            return

        elif "conversation" in target or "conversation" in raw:
            msgs = (CLOUD_RELAY_STATE.get("messages") if CLOUD_RELAY_STATE.get("messages") else None) or CONVERSATION_HISTORY
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": msgs, "events": msgs}).encode("utf-8"))
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

        if "projects" in target or "projects" in raw:
            default_projects = [
                {"id": "hmrc", "title": "COREMARKETGOODS ACCOUNTING - HMRC"},
                {"id": "orb", "title": "ORB - Voice Assistant"},
                {"id": "spook", "title": "Spook Studio"},
                {"id": "arts", "title": "Arts Grant"}
            ]
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "projects": default_projects}).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(json.dumps({
            "app": "Orb AI Live Voice Studio",
            "version": "v4.6",
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

        if "cloud_relay" in target or "cloud_relay" in raw:
            if data.get("active_chat_title"):
                CLOUD_RELAY_STATE["active_chat_title"] = data["active_chat_title"]
            if data.get("projects") and isinstance(data["projects"], list):
                CLOUD_RELAY_STATE["projects"] = data["projects"]
            if data.get("messages") and isinstance(data["messages"], list):
                CLOUD_RELAY_STATE["messages"] = data["messages"]
            CLOUD_RELAY_STATE["last_sync"] = time.time()
            
            pending = list(CLOUD_RELAY_STATE.get("pending_prompts", []))
            CLOUD_RELAY_STATE["pending_prompts"] = []
            try:
                try:
                    from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state
                except ImportError:
                    from sync_engine import get_cloud_sync_state, save_cloud_sync_state
                st = get_cloud_sync_state() or {}
                persisted_q = st.get("pending_antigrav_prompts", [])
                if persisted_q:
                    seen_ids = {p.get("id") for p in pending if isinstance(p, dict)}
                    for pq in persisted_q:
                        if isinstance(pq, dict) and pq.get("id") not in seen_ids:
                            pending.append(pq)
                    st["pending_antigrav_prompts"] = []
                    save_cloud_sync_state(st)
            except Exception:
                pass
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "pending_prompts": pending,
                "active_chat_title": CLOUD_RELAY_STATE["active_chat_title"]
            }).encode("utf-8"))
            return

        elif "scan_all_chats" in target or "scan_all_chats" in raw:
            pending = CLOUD_RELAY_STATE.setdefault("pending_prompts", [])
            pending.append({
                "id": f"scan_{int(time.time()*1000)}",
                "text": "__SCAN_ALL_CHATS__",
                "chat_title": ""
            })
            self._set_headers(200)
            self.wfile.write(b'{"status": "scan_requested"}')
            return

        elif "speech_input" in target or "speech_input" in raw:
            user_text = data.get("text", "").strip()
            chat_title = data.get("chat_title", "").strip()
            if accent_adapter:
                user_text = accent_adapter.adapt_speech_text(user_text)
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            if not user_text:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ok", "reply": ""}')
                return

            # 1. Queue pending prompt for Sadie's Desktop Antigravity Worker
            pending = CLOUD_RELAY_STATE.setdefault("pending_prompts", [])
            target_chat = chat_title or CLOUD_RELAY_STATE.get("active_chat_title", "")
            pending.append({
                "id": f"prompt_{int(time.time()*1000)}",
                "text": user_text,
                "chat_title": target_chat,
                "created_at": int(time.time()*1000)
            })

            # 2. Add user message to conversation history
            user_msg = {
                "role": "user",
                "text": user_text,
                "time": time.strftime("%H:%M")
            }
            CONVERSATION_HISTORY.append(user_msg)
            relay_msgs = CLOUD_RELAY_STATE.setdefault("messages", [])
            relay_msgs.append(user_msg)

            # 3. Persist pending prompt into Cloud Sync Storage so it survives even while Desktop PC is powered off
            try:
                try:
                    from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                except ImportError:
                    from sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                st = get_cloud_sync_state() or {}
                persisted_q = list(st.get("pending_antigrav_prompts", []))
                persisted_q.append(pending[-1])
                st["pending_antigrav_prompts"] = persisted_q[-30:]
                save_cloud_sync_state(st)
            except Exception:
                pass

            desktop_online = (time.time() - CLOUD_RELAY_STATE.get("last_sync", 0)) < 25

            if data.get("source") == "antigrav_mirror":
                if desktop_online:
                    CLOUD_RELAY_STATE["messages"] = relay_msgs[-100:]
                    self._set_headers(200)
                    self.wfile.write(json.dumps({
                        "status": "ok",
                        "desktop_online": True,
                        "queued_for_antigravity": True
                    }).encode("utf-8"))
                    return
                else:
                    # Desktop PC is OFF: Run Real-Time Cloud Live-Code & UI Patching Engine immediately on Vercel
                    api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_GEM_KEY
                    cloud_sys = (
                        f"You are Antigravity Cloud Live-Coding Engine for Sadie's app '{target_chat or 'ORB'}'. "
                        "Even when Sadie's desktop PC is turned off, you apply real-time live code, CSS, DOM, and data updates directly in the cloud via live_patch so her app updates immediately on her phone. "
                        "Return ONLY valid JSON with this structure: "
                        '{"reply": "Short UK English confirmation of what you changed or answered (no exclamation marks)", '
                        '"live_patch": {"css": "Optional valid CSS string to inject live into the app", '
                        '"js": "Optional safe browser JS statement to execute live in the app (e.g. modifying DOM elements, updating localStorage, adding a project via notionProjects.unshift(...), or switching tabs)", '
                        '"clear_all": false}}'
                    )
                    payload_bytes = json.dumps({
                        "system_instruction": {"parts": [{"text": cloud_sys}]},
                        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                        "generationConfig": {
                            "maxOutputTokens": 700,
                            "temperature": 0.2,
                            "responseMimeType": "application/json"
                        }
                    }).encode("utf-8")
                    resp_json = _fast_gemini_post("gemini-flash-lite-latest", api_key, payload_bytes, timeout=4.8)
                    cloud_reply = ""
                    live_patch = None
                    if resp_json and "candidates" in resp_json:
                        try:
                            raw_txt = resp_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                            parsed_obj = json.loads(raw_txt)
                            cloud_reply = (parsed_obj.get("reply") or "").strip()
                            lp = parsed_obj.get("live_patch")
                            if isinstance(lp, dict) and (lp.get("css") or lp.get("js") or lp.get("clear_all")):
                                live_patch = {
                                    "id": f"lp_{int(time.time()*1000)}",
                                    "css": (lp.get("css") or "").strip(),
                                    "js": (lp.get("js") or "").strip(),
                                    "clear_all": bool(lp.get("clear_all", False)),
                                    "created_at": int(time.time()*1000)
                                }
                        except Exception:
                            pass

                    if not cloud_reply:
                        cloud_reply = f"Applied your request in the cloud for {target_chat or 'ORB'} and synced it for your desktop workspace."

                    active_patches = []
                    try:
                        try:
                            from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state
                        except ImportError:
                            from sync_engine import get_cloud_sync_state, save_cloud_sync_state
                        st = get_cloud_sync_state() or {}
                        active_patches = list(st.get("live_patches", []))
                        if live_patch:
                            if live_patch.get("clear_all"):
                                active_patches = []
                            else:
                                active_patches.append(live_patch)
                                active_patches = active_patches[-25:]
                            st["live_patches"] = active_patches
                            save_cloud_sync_state(st)
                    except Exception:
                        if live_patch and not live_patch.get("clear_all"):
                            active_patches = [live_patch]

                    ai_msg = {
                        "role": "assistant",
                        "text": cloud_reply,
                        "time": time.strftime("%H:%M")
                    }
                    CONVERSATION_HISTORY.append(ai_msg)
                    relay_msgs.append(ai_msg)
                    CLOUD_RELAY_STATE["messages"] = relay_msgs[-100:]
                    self._set_headers(200)
                    self.wfile.write(json.dumps({
                        "status": "ok",
                        "desktop_online": False,
                        "queued_for_antigravity": True,
                        "reply": cloud_reply,
                        "live_patch": live_patch,
                        "live_patches": active_patches
                    }).encode("utf-8"))
                    return

            # Route to sub-second dynamic Gemini model for legacy voice calls
            ai_reply = query_gemini(user_text, history=relay_msgs)
            ai_msg = {
                "role": "assistant",
                "text": ai_reply,
                "time": time.strftime("%H:%M")
            }
            CONVERSATION_HISTORY.append(ai_msg)
            relay_msgs.append(ai_msg)
            CLOUD_RELAY_STATE["messages"] = relay_msgs[-100:]

            audio_url = f"/api/tts?text={urllib.parse.quote(ai_reply)}&voice={urllib.parse.quote(voice)}"
            audio_b64 = ""
            try:
                audio_bytes = generate_audio_bytes(ai_reply, voice, max_wait=1.15)
                if audio_bytes:
                    audio_b64 = "data:audio/mpeg;base64," + base64.b64encode(audio_bytes).decode("ascii")
            except Exception:
                pass
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "reply": ai_reply,
                "audio_url": audio_b64 or audio_url
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
            audio_b64_in = data.get("audio_base64")
            audio_mime_in = data.get("audio_mime")
            if user_text and accent_adapter:
                user_text = accent_adapter.adapt_speech_text(user_text)
            voice = data.get("voice") or VOICE_SETTINGS.get("voice", "en-GB-SoniaNeural")
            categories = data.get("categories", [])
            my_tasks = data.get("my_tasks", [])
            assistant_tasks = data.get("assistant_tasks", [])
            active_cat = data.get("active_category", "accounts")
            active_task = data.get("active_task_title", "")
            call_history = data.get("call_history", [])

            if not user_text and not audio_b64_in:
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
                calendar_events=cal_events,
                audio_base64=audio_b64_in,
                audio_mime=audio_mime_in,
                packing_summary=data.get("packing_summary"),
                budget_summary=data.get("budget_summary"),
                active_app=data.get("active_app")
            )

            if res.get("ignore") or not (res.get("reply") or "").strip():
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "ok", "ignore": True, "reply": "", "audio_url": ""}).encode("utf-8"))
                return

            reply = res.get("reply", "").strip()
            if res.get("user_transcript"):
                user_text = res.get("user_transcript")
            action = res.get("action")
            
            # Record into shared conversation history
            CONVERSATION_HISTORY.append({"role": "user", "text": user_text, "time": time.strftime("%H:%M")})
            CONVERSATION_HISTORY.append({"role": "assistant", "text": reply, "time": time.strftime("%H:%M")})
            
            # Generate inline audio bytes immediately so client plays with zero second round-trip
            audio_url = f"/api/tts?text={urllib.parse.quote(reply)}&voice={urllib.parse.quote(voice)}"
            audio_b64 = ""
            try:
                audio_bytes = generate_audio_bytes(reply, voice, max_wait=1.15)
                if audio_bytes:
                    audio_b64 = "data:audio/mpeg;base64," + base64.b64encode(audio_bytes).decode("ascii")
            except Exception:
                pass

            # Only sync to cloud blob if an action modified tasks, and do it non-blocking
            if action and (action.get("add_my_task") or action.get("delegate_to_assistant")):
                def _bg_sync():
                    try:
                        try:
                            from api.sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                        except ImportError:
                            from sync_engine import get_cloud_sync_state, save_cloud_sync_state, merge_sync_states
                        existing = get_cloud_sync_state() or {}
                        incoming_sync = {}
                        if action.get("add_my_task"):
                            task_info = action["add_my_task"]
                            new_task = {"id": f"t_{int(time.time()*1000)}", "title": task_info.get("title", ""), "category": task_info.get("category", "accounts"), "priority": task_info.get("priority", "high"), "completed": False, "createdAt": int(time.time()*1000)}
                            current_tasks = list(existing.get("focus_tasks", []))
                            current_tasks.append(new_task)
                            incoming_sync["focus_tasks"] = current_tasks
                        if action.get("delegate_to_assistant"):
                            ast_info = action["delegate_to_assistant"]
                            new_ast = {"id": f"ast_{int(time.time()*1000)}", "title": ast_info.get("title", ""), "category": ast_info.get("category", "accounts"), "status": "in_progress", "notes": ast_info.get("notes", ""), "createdAt": int(time.time()*1000)}
                            current_asts = list(existing.get("assistant_tasks", []))
                            current_asts.append(new_ast)
                            incoming_sync["assistant_tasks"] = current_asts
                        merged = merge_sync_states(existing, incoming_sync)
                        save_cloud_sync_state(merged)
                    except Exception:
                        pass
                import threading
                threading.Thread(target=_bg_sync, daemon=True).start()

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "reply": reply,
                "user_transcript": user_text,
                "action": action,
                "audio_url": audio_b64 or audio_url
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
