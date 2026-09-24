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
import threading
import ctypes
from ctypes import wintypes
import pyperclip
import urllib.parse
import urllib.request
import glob
from http.server import HTTPServer, BaseHTTPRequestHandler
import edge_tts

BRAIN_DIR = r"C:\Users\corem\.gemini\antigravity\brain"
FALLBACK_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web_app")
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")
CONVERSATION_FILE = os.path.join(BASE_DIR, "live_conversation.json")
CHAT_VOICES_FILE = os.path.join(BASE_DIR, "chat_voices.json")
TEMP_AUDIO = os.path.join(BASE_DIR, "speech_test.mp3")
PORT = 8766


def load_chat_voices():
    if os.path.exists(CHAT_VOICES_FILE):
        try:
            with open(CHAT_VOICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"announce_chat": True, "default_voice": "en-GB-SoniaNeural", "chats": {}}


def save_chat_voices(cfg):
    try:
        with open(CHAT_VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[VOICE-CFG] Error saving chat voices: {e}", flush=True)


KNOWN_PROJECTS = {
    "coremarketgoods accounting": "Orb",
    "coremarketgoods": "Orb",
    "orb": "Orb",
    "orb ai voice studio v1": "Orb",
    "orb ai voice studio": "Orb",
    "timber builds": "Timber Builds",
    "snap n pack app": "Snap N Pack",
    "snap n pack": "Snap N Pack",
    "lead collect": "Lead Collect",
    "thermo retreats designer": "Thermo Retreats",
    "thermo retreats": "Thermo Retreats",
    "blogflow": "BlogFlow",
    "festi face": "Festi Face",
    "glitterandshots": "Glitter & Shots",
    "spook studio": "Spook Studio",
}

def format_project_title(raw):
    if not raw:
        return ""
    unquoted = urllib.parse.unquote(str(raw))
    clean = re.sub(r"['\"’“”#]+", "", unquoted).strip()
    clean = re.sub(r"^(?:Implementation Plan|Walkthrough|Plan|Verification Plan)[:\s-]+", "", clean, flags=re.I).strip()
    clean = re.sub(r"\s*-\s*(?:Implementation Plan|Walkthrough|Verification|Plan).*$", "", clean, flags=re.I).strip()
    clean = re.sub(r"\s*-\s*HMRC\b", "", clean, flags=re.I).strip()
    clean = clean.replace("_", " ").replace("-", " ")
    
    clean_low = re.sub(r"\s+", " ", clean).lower().strip()
    if clean_low in KNOWN_PROJECTS:
        return KNOWN_PROJECTS[clean_low]
    for k, v in KNOWN_PROJECTS.items():
        if k in clean_low:
            return v

    words = clean.split()
    formatted = []
    for w in words:
        wl = w.lower()
        if wl in ("hmrc", "adhd", "vat", "ltd", "llc", "ai", "p&l", "api", "ui", "ux"):
            formatted.append(wl.upper())
        elif wl == "coremarketgoods":
            formatted.append("Orb")
        elif wl == "orb":
            formatted.append("Orb")
        elif wl == "snapnpack":
            formatted.append("Snap N Pack")
        elif wl in ("dostuff", "dostuff:"):
            formatted.append("DoStuff")
        else:
            formatted.append(w.capitalize())
    res = " ".join(formatted)
    return res if len(res) <= 38 else res[:38] + "..."

def is_garbage_title(cand):
    if not cand or len(cand) < 2:
        return True
    cl = cand.lower().strip()
    if any(cl.startswith(s) for s in ("i am ", "i want", "can you", "could you", "please", "agent ", "assistant", "http", "v1", "laptop", "tablet")):
        return True
    if any(ch in cand for ch in ("?", "=", "!", "{", "}", ";")):
        return True
    return False

def extract_chat_title(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return "Orb"

    chat_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(transcript_path))))
    cid = os.path.basename(chat_dir)

    # 1. First priority: Custom label from chat_voices.json
    if os.path.exists(CHAT_VOICES_FILE):
        try:
            with open(CHAT_VOICES_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                chat = cfg.get("chats", {}).get(cid, {})
                cand = chat.get("label") or chat.get("title")
                if cand and not is_garbage_title(cand):
                    return cand
        except Exception:
            pass
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(80):
                line = f.readline()
                if not line: break

                norm = urllib.parse.unquote(line.replace("\\\\", "/").replace("\\", "/"))

                matches = re.findall(r'(?:[a-zA-Z]:|users/[^/]+|onedrive)/desktop/([^/\"\'\<\>\r\n]+)', norm, re.I)
                for fld in matches:
                    fld_clean = fld.strip()
                    if fld_clean and fld_clean.lower() not in (
                        "scratch", "logs", "tasks", ".system_generated", "brain", 
                        "system_generated", "temp_audio", "new folder (2)", "desktop"
                    ):
                        formatted = format_project_title(fld_clean)
                        if formatted and not is_garbage_title(formatted):
                            return formatted

                if "->" in norm:
                    m = re.search(r'([a-zA-Z]:/[^\r\n"\'->]+)\s*->', norm)
                    if m:
                        folder = m.group(1).rstrip("/").split("/")[-1]
                        if folder:
                            formatted = format_project_title(folder)
                            if formatted and not is_garbage_title(formatted):
                                return formatted
    except Exception:
        pass

    # 2. Second priority: implementation_plan.md or walkthrough.md in chat directory
    for doc in ("implementation_plan.md", "walkthrough.md"):
        doc_path = os.path.join(chat_dir, doc)
        if os.path.exists(doc_path):
            try:
                with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                    for _ in range(8):
                        l = f.readline()
                        if l.startswith("# "):
                            raw_t = l[2:].strip()
                            t = format_project_title(raw_t)
                            if t and not is_garbage_title(t) and t.lower() not in (
                                "goal description", "walkthrough", "implementation plan", "user review required"
                            ):
                                return t
            except Exception:
                pass

    # 3. Third priority: Custom label from chat_voices.json (if clean and not a sentence)
    if os.path.exists(CHAT_VOICES_FILE):
        try:
            with open(CHAT_VOICES_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                chat = cfg.get("chats", {}).get(cid, {})
                cand = chat.get("label") or chat.get("title")
                if cand and not is_garbage_title(cand):
                    return cand
        except Exception:
            pass

    return "Coremarket Goods Accounting"


def get_active_chat_title_and_transcript():
    try:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk: u32.SetThreadDesktop(h_desk)
        
        title_box = [""]
        def enum_cb(hwnd, lparam):
            if u32.IsWindowVisible(hwnd):
                pid = wintypes.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                h_proc = k32.OpenProcess(0x1000, False, pid.value)
                if h_proc:
                    try:
                        exe_buff = ctypes.create_unicode_buffer(1024)
                        size = wintypes.DWORD(1024)
                        if k32.QueryFullProcessImageNameW(h_proc, 0, exe_buff, ctypes.byref(size)):
                            exe_name = exe_buff.value.lower()
                            if any(x in exe_name for x in ("antigravity", "cursor", "code")):
                                length = u32.GetWindowTextLengthW(hwnd)
                                if length > 0:
                                    buff = ctypes.create_unicode_buffer(length + 1)
                                    u32.GetWindowTextW(hwnd, buff, length + 1)
                                    t = buff.value.strip()
                                    if t and not title_box[0]:
                                        title_box[0] = t
                    finally:
                        k32.CloseHandle(h_proc)
            return True
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        cb = EnumWindowsProc(enum_cb)
        u32.EnumWindows(cb, 0)

        window_title = title_box[0]
        transcripts = glob.glob(os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl"))
        transcripts.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        if window_title and window_title.lower() not in ("antigravity", "antigravity.exe", "cursor", "cursor.exe", "code", "code.exe", "visual studio code"):
            clean_win = re.sub(r'[^a-zA-Z0-9 ]', '', window_title.lower()).strip()
            win_words = set(clean_win.split())
            if win_words:
                for p in transcripts:
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            for _ in range(50):
                                line = f.readline()
                                if not line: break
                                d = json.loads(line)
                                cnt = re.sub(r'[^a-zA-Z0-9 ]', '', d.get("content", "").lower())
                                cnt_words = set(cnt.split())
                                if len(win_words.intersection(cnt_words)) >= min(2, len(win_words)):
                                    proj_title = extract_chat_title(p)
                                    return proj_title, p
                    except Exception:
                        pass

        if transcripts:
            friendly_title = extract_chat_title(transcripts[0])
            return friendly_title or "Orb AI Project", transcripts[0]
    except Exception:
        pass
    return "Orb AI Project", FALLBACK_LOG


def get_latest_transcript_path():
    _, path = get_active_chat_title_and_transcript()
    return path

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
        "silence_timeout": 5.0,
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
                data = json.load(f)
                if data.get("is_speaking", False) and (time.time() - data.get("timestamp", 0) > 10):
                    data["is_speaking"] = False
                    data["current_text"] = ""
                return data
        except Exception:
            pass
    return {"is_speaking": False, "current_text": ""}


def update_live_state(is_speaking=False, current_text="", stop_requested=False):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "is_speaking": is_speaking,
                "current_text": current_text,
                "stop_requested": stop_requested,
                "timestamp": time.time()
            }, f)
    except Exception:
        pass


def clean_words(text):
    return [w for w in re.sub(r'[^a-z0-9 ]', ' ', text.lower()).split() if w]


def find_longest_common_phrase(words1, words2):
    set2_str = ' ' + ' '.join(words2) + ' '
    max_len = 0
    for i in range(len(words1)):
        for j in range(i + 4, min(len(words1) + 1, i + 35)):
            phrase = ' ' + ' '.join(words1[i:j]) + ' '
            if phrase in set2_str:
                max_len = max(max_len, j - i)
    return max_len


def is_echo_of_ai(text):
    if not text:
        return True
    user_words = clean_words(text)
    if len(user_words) < 4:
        return False

    ai_texts = []
    st = load_live_state()
    curr = st.get("current_text", "").strip()
    if curr:
        ai_texts.append(curr)

    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                for item in history[:15]:
                    txt = item.get("text", "").strip()
                    if txt:
                        ai_texts.append(txt)
        except Exception:
            pass

    for ai_t in ai_texts:
        ai_words = clean_words(ai_t)
        if not ai_words:
            continue
        max_seq = find_longest_common_phrase(user_words, ai_words)
        if max_seq >= 4:
            return True

    return False


def strip_ai_echo(text):
    if not text:
        return ""
    cleaned = text.strip()
    if not cleaned:
        return ""

    if is_echo_of_ai(cleaned):
        safe_preview = cleaned[:70].encode("ascii", "ignore").decode("ascii")
        print(f"[ECHO-SHIELD] Discarded acoustic speaker echo: '{safe_preview}...'", flush=True)
        return ""

    return cleaned


def get_conversation_history(limit=100):
    messages = []
    log_path = get_latest_transcript_path()
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
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
                        
                        clean_cnt = cnt.strip()
                        m = re.search(r'<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>', clean_cnt, re.DOTALL)
                        if m:
                            clean_cnt = m.group(1).strip()

                        messages.append({
                            "role": "user",
                            "text": clean_cnt,
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
    try:
        import miniaudio
        import sounddevice as sd
        decoded = miniaudio.mp3_read_file_f32(filepath)
        sd.play(decoded.samples, decoded.sample_rate)
        sd.wait()
        return
    except Exception as e:
        print(f"[AUDIO-PLAY-ERR]: {e}", flush=True)

    abs_path = os.path.abspath(filepath)
    alias = f"test_{int(time.time() * 1000) % 10000}"
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
    if ret == 0:
        winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
        winmm.mciSendStringW(f"close {alias}", None, 0, None)


def clean_markdown_for_speech(text):
    if not text:
        return ""
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\b(e\.g\.|eg)\b", "for example,", text, flags=re.I)
    text = re.sub(r"\b(i\.e\.|ie)\b", "that is,", text, flags=re.I)
    text = re.sub(r"\betc\b\.?", "and so on", text, flags=re.I)
    text = re.sub(r"\b(vs\.|vs)\b", "versus", text, flags=re.I)
    lines = []
    for raw_line in text.split("\n"):
        l = raw_line.strip()
        l = re.sub(r"^[0-9]+[\.\)]\s*", "", l)
        l = re.sub(r"^[#>*\-]+\s*", "", l)
        l = re.sub(r"[*_~]+", "", l).strip()
        if l:
            if not l.endswith((".", "!", "?", ":", ";", ",")):
                l += "."
            lines.append(l)
    res = " ".join(lines)
    return re.sub(r"\s+", " ", res).strip()


INCOMING_QUEUE_FILE = os.path.join(BASE_DIR, "speech_queue_incoming.jsonl")


def enqueue_speech_request(text, label="Orb AI Assistant", cid="manual"):
    if not text or not text.strip():
        return False
    req = {
        "cid": cid,
        "label": label,
        "text": text.strip(),
        "queued_at": time.time()
    }
    try:
        with open(INCOMING_QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(req) + "\n")
        return True
    except Exception as e:
        print(f"[QUEUE-ERROR]: {e}", flush=True)
        return False


def trigger_replay_last_ai_reply():
    msgs = get_conversation_history(limit=50)
    last_reply = ""
    for m in reversed(msgs):
        if m.get("role") == "assistant" and m.get("text"):
            last_reply = m.get("text")
            break
    if not last_reply:
        return {"status": "no_reply_found"}

    cleaned = clean_markdown_for_speech(last_reply)
    if len(cleaned) > 2500:
        cleaned = cleaned[:2500] + "..."

    active_title, _ = get_active_chat_title_and_transcript()
    label = active_title or "Orb AI Assistant"
    enqueue_speech_request(cleaned, label=label, cid="replay")
    return {"status": "queued", "text": cleaned[:80]}


class PWAHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        url_path = self.path.split("?")[0]
        if url_path in ["/", "/index.html", "/widget"]:
            file_path = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._set_headers(200, "text/html; charset=utf-8")
                self.wfile.write(content.encode("utf-8"))
            else:
                self._set_headers(404)
        elif url_path in ["/accounting", "/hub", "/accounting_hub.html"]:
            file_path = os.path.join(WEB_DIR, "accounting_hub.html")
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
            settings = load_settings()
            state["enabled"] = settings.get("enabled", True)
            active_title, _ = get_active_chat_title_and_transcript()
            state["active_chat_title"] = active_title
            idx_path = os.path.join(WEB_DIR, "index.html")
            state["app_version"] = int(os.path.getmtime(idx_path) * 1000) if os.path.exists(idx_path) else 0
            self._set_headers(200)
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif url_path == "/api/app_version":
            idx_path = os.path.join(WEB_DIR, "index.html")
            mtime = os.path.getmtime(idx_path) if os.path.exists(idx_path) else 0
            self._set_headers(200)
            self.wfile.write(json.dumps({"version": int(mtime * 1000)}).encode("utf-8"))
        elif url_path == "/api/conversation":
            limit = 100
            if "?" in self.path:
                try:
                    parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    if "limit" in parsed_q:
                        limit = int(parsed_q["limit"][0])
                except Exception:
                    pass
            conv = get_conversation_history(limit)
            self._set_headers(200)
            self.wfile.write(json.dumps({"messages": conv}).encode("utf-8"))
        elif url_path == "/api/chat_voices":
            cfg = load_chat_voices()
            self._set_headers(200)
            self.wfile.write(json.dumps(cfg).encode("utf-8"))
        elif url_path.startswith("/Bank_Statements"):
            import mimetypes
            rel = url_path.lstrip("/").replace("%20", " ")
            local_path = os.path.join(BASE_DIR, rel)
            if not os.path.exists(local_path):
                thermo_path = os.path.join(r"C:\Users\corem\Desktop\THERMO RETREATS LTD  FILLING ACCOUNTS", rel)
                if os.path.exists(thermo_path):
                    local_path = thermo_path
            
            if os.path.exists(local_path) and os.path.isfile(local_path):
                mime, _ = mimetypes.guess_type(local_path)
                if not mime:
                    mime = "application/pdf" if local_path.lower().endswith(".pdf") else ("text/csv" if local_path.lower().endswith(".csv") else "application/octet-stream")
                try:
                    with open(local_path, "rb") as f:
                        file_data = f.read()
                    self._set_headers(200, mime)
                    self.wfile.write(file_data)
                except Exception as e:
                    self._set_headers(500, "text/plain")
                    self.wfile.write(str(e).encode("utf-8"))
            else:
                try:
                    proxy_url = f"http://127.0.0.1:5500{self.path}"
                    with urllib.request.urlopen(proxy_url, timeout=10) as p_res:
                        p_data = p_res.read()
                        mime = p_res.headers.get("Content-Type", "application/octet-stream")
                        self._set_headers(p_res.status, mime)
                        self.wfile.write(p_data)
                except Exception as pe:
                    self._set_headers(404, "text/plain")
                    self.wfile.write(b"Statement file not found")
        elif url_path in ["/api/get-transactions", "/api/list-statements", "/api/fetch-address"]:
            try:
                proxy_url = f"http://127.0.0.1:5500{self.path}"
                with urllib.request.urlopen(proxy_url, timeout=5) as p_res:
                    p_data = p_res.read()
                    self._set_headers(p_res.status, "application/json")
                    self.wfile.write(p_data)
            except Exception as pe:
                self._set_headers(500, "application/json")
                self.wfile.write(json.dumps({"status": "error", "message": str(pe)}).encode("utf-8"))
        elif url_path == "/api/audio_preview":
            if os.path.exists(TEMP_AUDIO):
                with open(TEMP_AUDIO, "rb") as f:
                    audio_data = f.read()
                self._set_headers(200, "audio/mpeg")
                self.wfile.write(audio_data)
            else:
                self._set_headers(404)
        elif url_path == "/api/voice_preview_audio":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            v_id = query.get("voice", [""])[0]
            cache_file = os.path.join(BASE_DIR, "voice_cache", f"{v_id}.mp3")
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
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

        elif self.path == "/api/chat_voices":
            cfg = load_chat_voices()
            if "announce_chat" in data:
                cfg["announce_chat"] = bool(data["announce_chat"])
            if "default_voice" in data:
                cfg["default_voice"] = data["default_voice"]
            if "chats" in data and isinstance(data["chats"], dict):
                for cid, c_data in data["chats"].items():
                    if cid in cfg.setdefault("chats", {}):
                        cfg["chats"][cid].update(c_data)
                    else:
                        cfg["chats"][cid] = c_data
            save_chat_voices(cfg)
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "saved", "chat_voices": cfg}).encode("utf-8"))

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
                try:
                    import accent_adapter
                    text = accent_adapter.adapt_speech_text(text)
                except Exception:
                    pass
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

        elif self.path == "/api/polish_text":
            raw_text = data.get("text", "").strip()
            if not raw_text:
                self._set_headers(200)
                self.wfile.write(b'{"status": "ok", "polished": ""}')
                return

            polished = raw_text
            try:
                import accent_adapter
                polished = accent_adapter.adapt_speech_text(raw_text)
            except Exception:
                pass

            settings = load_settings()
            api_key = data.get("api_key") or settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")

            if api_key:
                models_to_try = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
                payload = {
                    "system_instruction": {
                        "parts": [{"text": "You are an expert AI Speech Polisher (Gemini / TextBlaze style). Transform raw, messy, or rambling spoken voice transcripts into clear, articulate, natural, well-phrased English. Fix speech errors, misheard words, filler words, and awkward grammar while strictly keeping the speaker's original meaning and voice. Return ONLY the final polished text with no surrounding quotes, no markdown explanations, and no preamble."}]
                    },
                    "contents": [{"parts": [{"text": raw_text}]}],
                    "generationConfig": {
                        "maxOutputTokens": 2048,
                        "temperature": 0.2
                    }
                }

                for mod in models_to_try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
                    try:
                        req = urllib.request.Request(
                            url,
                            data=json.dumps(payload).encode("utf-8"),
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            resp_data = json.loads(resp.read().decode("utf-8"))
                            candidate = resp_data.get("candidates", [{}])[0]
                            parts = candidate.get("content", {}).get("parts", [])
                            if parts and parts[0].get("text"):
                                ai_text = parts[0]["text"].strip()
                                if (ai_text.startswith('"') and ai_text.endswith('"')) or (ai_text.startswith("'") and ai_text.endswith("'")):
                                    ai_text = ai_text[1:-1].strip()
                                if ai_text:
                                    polished = ai_text
                                    break
                    except Exception as e:
                        print(f"[POLISH-ERR] ({mod}): {e}", flush=True)

            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "polished": polished}).encode("utf-8"))

        elif self.path == "/api/stop":
            update_live_state(is_speaking=False, current_text="", stop_requested=True)
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            in_queue = os.path.join(BASE_DIR, "speech_queue_incoming.jsonl")
            if os.path.exists(in_queue):
                try:
                    with open(in_queue, "w", encoding="utf-8") as f:
                        f.truncate(0)
                except Exception:
                    pass
            self._set_headers(200)
            self.wfile.write(b'{"status": "stopped"}')

        elif self.path == "/api/pause_total":
            total_pause = data.get("total_pause", True)
            settings = load_settings()
            settings["enabled"] = not total_pause
            save_settings(settings)
            if total_pause:
                update_live_state(is_speaking=False, current_text="", stop_requested=True)
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception:
                    pass
                in_queue = os.path.join(BASE_DIR, "speech_queue_incoming.jsonl")
                if os.path.exists(in_queue):
                    try:
                        with open(in_queue, "w", encoding="utf-8") as f:
                            f.truncate(0)
                    except Exception:
                        pass
            else:
                update_live_state(is_speaking=False, current_text="", stop_requested=False)
                # Signal auto_voice_reader to scan all chats for missed replies
                try:
                    with open(os.path.join(BASE_DIR, "scan_all_chats.signal"), "w", encoding="utf-8") as f:
                        f.write("1")
                except Exception:
                    pass
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "total_pause": total_pause, "enabled": settings["enabled"]}).encode("utf-8"))

        elif self.path in ("/api/read_ai_reply", "/api/speak_last", "/api/kickstart"):
            settings = load_settings()
            settings["enabled"] = True
            save_settings(settings)
            res = trigger_replay_last_ai_reply()
            # Also trigger scan across all chats if no direct reply was queued
            if res.get("status") == "no_reply_found":
                try:
                    with open(os.path.join(BASE_DIR, "scan_all_chats.signal"), "w", encoding="utf-8") as f:
                        f.write("1")
                except Exception:
                    pass
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif self.path == "/api/scan_all_chats":
            try:
                with open(os.path.join(BASE_DIR, "scan_all_chats.signal"), "w", encoding="utf-8") as f:
                    f.write("1")
            except Exception:
                pass
            self._set_headers(200)
            self.wfile.write(b'{"status": "scan_requested"}')

        elif self.path == "/api/test":
            text = data.get("text", "Hello Sadie! This is your voice preview.")
            req_voice = data.get("voice")
            settings = load_settings()
            if req_voice:
                settings["voice"] = req_voice
                save_settings(settings)

            enqueue_speech_request(text, label="Voice Preview", cid="preview")
            self._set_headers(200)
            self.wfile.write(json.dumps({"status": "queued"}).encode("utf-8"))

        elif self.path == "/api/pin_taskbar":
            import subprocess
            import tempfile
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            tb_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar")
            edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if not os.path.exists(edge_exe):
                edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            browser_exe = edge_exe if os.path.exists(edge_exe) else (chrome_exe if os.path.exists(chrome_exe) else "msedge.exe")

            app_target_url = "http://localhost:8766"
            app_args = f'--app={app_target_url} --window-size=460,720'

            shortcut_created = False
            for target_dir in [desktop_dir, tb_dir]:
                try:
                    if os.path.exists(target_dir):
                        lnk_path = os.path.join(target_dir, "Orb Voice Studio.lnk")
                        vbs_script = (
                            f'Set oWS = WScript.CreateObject("WScript.Shell")\n'
                            f'Set oLink = oWS.CreateShortcut("{lnk_path}")\n'
                            f'oLink.TargetPath = "{browser_exe}"\n'
                            f'oLink.Arguments = "{app_args}"\n'
                            f'oLink.Description = "Orb AI Voice Studio"\n'
                            f'oLink.Save\n'
                        )
                        vbs_path = os.path.join(tempfile.gettempdir(), "create_orb_sc.vbs")
                        with open(vbs_path, "w", encoding="utf-8") as vf:
                            vf.write(vbs_script)
                        subprocess.run(["cscript", "//nologo", vbs_path], check=False, timeout=5)
                        if os.path.exists(lnk_path):
                            shortcut_created = True
                except Exception as se:
                    print(f"[PIN-SC-ERR]: {se}", flush=True)

            # Launch standalone window so user can immediately see it on taskbar
            try:
                subprocess.Popen([browser_exe, f"--app={app_target_url}", "--window-size=460,720"])
            except Exception as le:
                print(f"[PIN-LAUNCH-ERR]: {le}", flush=True)
                bat_path = os.path.join(BASE_DIR, "LAUNCH_FLOATING_ORB.bat")
                try:
                    subprocess.Popen(["cmd.exe", "/c", bat_path], shell=False)
                except Exception:
                    pass

            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "ok",
                "shortcut_created": shortcut_created,
                "message": "Standalone app launched! Right-click the Orb icon on your Windows Taskbar and click 'Pin to taskbar'."
            }).encode("utf-8"))
        elif self.path in ["/api/upload-statement", "/api/delete-statement"]:
            try:
                proxy_url = f"http://127.0.0.1:5500{self.path}"
                req = urllib.request.Request(proxy_url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as p_res:
                    p_data = p_res.read()
                    self._set_headers(p_res.status, "application/json")
                    self.wfile.write(p_data)
            except Exception as pe:
                self._set_headers(500, "application/json")
                self.wfile.write(json.dumps({"status": "error", "message": str(pe)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')

    def log_message(self, format, *args):
        return


def keep_orb_pinned_loop():
    try:
        u32 = ctypes.windll.user32
        h_desk = u32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            u32.SetThreadDesktop(h_desk)

        u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u32.SetWindowPos.restype = wintypes.BOOL
        u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t

        HWND_TOPMOST = -1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        WS_EX_TOPMOST = 0x00000008

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        while True:
            try:
                def enum_cb(hwnd, lparam):
                    if u32.IsWindowVisible(hwnd):
                        length = u32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            u32.GetWindowTextW(hwnd, buff, length + 1)
                            t = buff.value.lower()
                            if "orb ai" in t or "orb voice studio" in t or "orb floating" in t:
                                ex = u32.GetWindowLongPtrW(hwnd, -20)
                                if not (ex & WS_EX_TOPMOST):
                                    u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                    return True
                u32.EnumWindows(EnumWindowsProc(enum_cb), 0)
            except Exception:
                pass
            time.sleep(0.8)
    except Exception:
        pass


def run():
    threading.Thread(target=keep_orb_pinned_loop, daemon=True).start()
    server_address = ("127.0.0.1", PORT)
    while True:
        try:
            httpd = HTTPServer(server_address, PWAHandler)
            print(f"Orb AI Voice Assistant live at http://localhost:{PORT}", flush=True)
            httpd.serve_forever()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[SERVER-ERR]: {e}", flush=True)
            time.sleep(1)


if __name__ == "__main__":
    run()

