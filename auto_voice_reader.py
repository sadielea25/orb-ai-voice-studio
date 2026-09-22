"""
auto_voice_reader.py
Ultra-fluid, direct hardware conversational voice reader.
Uses miniaudio + sounddevice for instantaneous auto-switching between Headphones (budi 50) and Laptop Speakers (Realtek).
"""

import os
import sys
import time
import json
import re
import asyncio
import collections
import threading
import glob
import urllib.parse
import edge_tts
import miniaudio
import numpy as np
import sounddevice as sd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = r"C:\Users\corem\.gemini\antigravity\brain"
FALLBACK_LOG = r"C:\Users\corem\.gemini\antigravity\brain\de5a4648-5c35-4b63-a84f-33cf8597b3ff\.system_generated\logs\transcript.jsonl"
SETTINGS_FILE = os.path.join(BASE_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(BASE_DIR, "speech_history.json")
STATE_FILE = os.path.join(BASE_DIR, "speech_live_state.json")


import ctypes
from ctypes import wintypes

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
                            if "antigravity.exe" in exe_buff.value.lower():
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

        if window_title and window_title.lower() not in ("antigravity", "antigravity.exe"):
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
                                    return window_title, p
                    except Exception:
                        pass

        if transcripts:
            friendly_title = extract_chat_title(transcripts[0])
            resolved_title = window_title if (window_title and window_title.lower() not in ("antigravity", "antigravity.exe")) else friendly_title
            return resolved_title or "Active Chat", transcripts[0]
    except Exception:
        pass
    return "Active Chat", FALLBACK_LOG


def get_latest_transcript_path():
    _, path = get_active_chat_title_and_transcript()
    return path


def load_settings():
    default = {
        "engine": "edge",
        "voice": "en-GB-SoniaNeural",
        "rate": "+10%",
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


def update_live_state(is_speaking=False, current_text="", stop_requested=False, device_name=""):
    state = {
        "is_speaking": is_speaking,
        "current_text": current_text,
        "stop_requested": stop_requested,
        "device_name": device_name,
        "timestamp": time.time(),
        "last_speech_end_time": time.time() if not is_speaking else 0.0
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


def get_active_output_device():
    """
    Dynamically finds the best physical output device:
    1. budi 50 / Bluetooth Headphones if connected
    2. Physical Realtek Speakers (laptop speakers)
    3. System default output
    """
    try:
        devices = sd.query_devices()
        budi_idx = None
        realtek_idx = None
        default_out = sd.default.device[1]

        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) > 0:
                name = d.get("name", "").lower()
                if "budi" in name:
                    budi_idx = i
                    break

        if budi_idx is not None:
            return budi_idx, devices[budi_idx]["name"]
        return None, "System Default"
    except Exception:
        return None, "System Default"


def clean_markdown_for_speech(text):
    if not text:
        return ""
    # Strip emojis
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    # Strip code blocks and inline code
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Convert markdown links to text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Strip URLs and HTML tags
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    # Natural spoken expansions so abbreviations aren't spelled out robotically
    text = re.sub(r"\b(e\.g\.|eg)\b", "for example,", text, flags=re.I)
    text = re.sub(r"\b(i\.e\.|ie)\b", "that is,", text, flags=re.I)
    text = re.sub(r"\betc\b\.?", "and so on", text, flags=re.I)
    text = re.sub(r"\b(vs\.|vs)\b", "versus", text, flags=re.I)
    text = re.sub(r"\s+/\s+", " or ", text)
    text = re.sub(r"&", " and ", text)
    # Preserve natural breathing pauses across paragraphs and list items
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
    res = re.sub(r"\s+", " ", res).strip()

    # Never truncate normal replies; only cap gigantic text dumps (> 800 chars)
    if len(res) > 800:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', res) if s.strip()]
        capped = []
        cur_len = 0
        for s in sentences:
            if cur_len + len(s) > 750:
                break
            capped.append(s)
            cur_len += len(s)
        if capped:
            res = " ".join(capped)

    return res


async def synthesize_speech_pcm(text, settings):
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

    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]

    if not audio_bytes:
        return None

    decoded = miniaudio.decode(
        audio_bytes,
        nchannels=2,
        sample_rate=44100,
        output_format=miniaudio.SampleFormat.SIGNED16
    )
    pcm = np.frombuffer(decoded.samples, dtype=np.int16).reshape(-1, 2)
    return pcm


def play_audio_pcm(pcm_data):
    if pcm_data is None or len(pcm_data) == 0:
        return

    dev_idx, dev_name = get_active_output_device()
    start_time = time.time()
    update_live_state(is_speaking=True, current_text="Speaking...", stop_requested=False, device_name=dev_name)

    try:
        if dev_idx is not None:
            try:
                sd.play(pcm_data, samplerate=44100, device=dev_idx)
            except Exception:
                sd.play(pcm_data, samplerate=44100)
        else:
            sd.play(pcm_data, samplerate=44100)

        duration = len(pcm_data) / 44100.0
        elapsed = 0.0

        while elapsed < duration:
            if check_stop_requested(start_time):
                try:
                    sd.stop()
                except Exception:
                    pass
                update_live_state(is_speaking=False, current_text="", stop_requested=False, device_name=dev_name)
                with queue_lock:
                    speech_queue.clear()
                print("\n[AUTO-SPEAKER] 🛑 Audio cut in by user! Stopped playback.", flush=True)
                return True
            time.sleep(0.03)
            elapsed = time.time() - start_time

        sd.wait()
        time.sleep(0.25)
    except Exception as e:
        print(f"[AUTO-SPEAKER] Playback error: {e}", flush=True)

    update_live_state(is_speaking=False, current_text="", stop_requested=False, device_name=dev_name)


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


CHAT_VOICES_FILE = os.path.join(BASE_DIR, "chat_voices.json")

DEFAULT_PALETTE = [
    {"id": "en-GB-SoniaNeural", "name": "Sonia (Adult British Female - Crisp & Professional)"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (Adult British Male - Friendly & Natural)"},
    {"id": "en-IE-EmilyNeural", "name": "Emily (Adult Irish Female - Warm & Melodic)"},
    {"id": "en-US-BrianMultilingualNeural", "name": "Brian (Adult Studio Male - Deep & Warm)"},
    {"id": "en-US-AvaMultilingualNeural", "name": "Ava (Adult Conversational Female - Expressive)"},
    {"id": "en-IE-ConnorNeural", "name": "Connor (Adult Irish Male - Smooth & Relaxed)"}
]


def load_chat_voices():
    default = {
        "announce_chat": False,
        "default_voice": "en-IE-EmilyNeural",
        "voice_palette": DEFAULT_PALETTE,
        "chats": {}
    }
    if os.path.exists(CHAT_VOICES_FILE):
        try:
            with open(CHAT_VOICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
                return default
        except Exception:
            pass
    return default


def save_chat_voices(cfg):
    try:
        with open(CHAT_VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[VOICE-CFG] Error saving chat voices: {e}", flush=True)


KNOWN_PROJECTS = {
    "coremarketgoods accounting": "Coremarket Goods Accounting",
    "coremarketgoods": "Coremarket Goods Accounting",
    "timber builds": "Timber Builds",
    "snap n pack app": "Snap N Pack",
    "snap n pack": "Snap N Pack",
    "lead collect": "Lead Collect",
    "thermo retreats designer": "Thermo Retreats",
    "thermo retreats": "Thermo Retreats",
    "blogflow": "BlogFlow",
    "festi face": "Festi Face",
    "glitterandshots": "Glitter & Shots",
    "orb ai voice studio v1": "Orb AI Voice Studio",
    "orb ai voice studio": "Orb AI Voice Studio",
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
            formatted.append("Coremarket Goods")
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
        return "Coremarket Goods Accounting"

    chat_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(transcript_path))))
    cid = os.path.basename(chat_dir)

    # 1. First priority: Workspace Directory from transcript.jsonl
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


def get_or_assign_chat_voice(cid, transcript_path):
    cfg = load_chat_voices()
    chats = cfg.setdefault("chats", {})
    if cid in chats:
        c = chats[cid]
        return c.get("label", "Assistant"), c.get("voice", cfg.get("default_voice", "en-IE-EmilyNeural")), c.get("rate", "+0%"), c.get("pitch", "+0Hz")

    palette = cfg.get("voice_palette", DEFAULT_PALETTE)
    assigned_voice = palette[len(chats) % len(palette)]["id"]

    extracted = extract_chat_title(transcript_path) if transcript_path else None
    label = extracted if extracted else f"Agent {len(chats) + 1}"

    chats[cid] = {
        "label": label,
        "title": label,
        "voice": assigned_voice,
        "rate": "+0%",
        "pitch": "+0Hz"
    }
    save_chat_voices(cfg)
    print(f"[AUTO-SPEAKER] 🎙 Automatically assigned voice '{assigned_voice}' to chat [{label}] ({cid[:8]})", flush=True)
    return label, assigned_voice, "+0%", "+0Hz"


speech_queue = collections.deque()
queue_lock = threading.Lock()
last_spoken_cid = None


def queue_speech(cid, text, transcript_path):
    if not load_settings().get("enabled", True):
        return
    cleaned = clean_markdown_for_speech(text)
    if not cleaned:
        return

    label = extract_chat_title(transcript_path) if transcript_path else None
    if not label or is_garbage_title(label):
        chat_cfg = load_chat_voices()
        chat_entry = chat_cfg.get("chats", {}).get(cid, {})
        cand = chat_entry.get("label") or chat_entry.get("title")
        if cand and not is_garbage_title(cand):
            label = cand
    if not label:
        label = "Coremarket Goods Accounting"

    with queue_lock:
        speech_queue.append({
            "cid": cid,
            "label": label,
            "text": cleaned,
            "queued_at": time.time()
        })
        q_len = len(speech_queue)
    live_settings = load_settings()
    current_voice = live_settings.get("voice", "en-GB-LibbyNeural")
    print(f"\n[AUTO-SPEAKER] 📥 Queued response from [{label}] (Live Orb Voice: {current_voice}, queue depth: {q_len})", flush=True)


INCOMING_QUEUE_FILE = os.path.join(BASE_DIR, "speech_queue_incoming.jsonl")


def check_incoming_queue_file():
    if not os.path.exists(INCOMING_QUEUE_FILE):
        return

    lines = []
    try:
        with open(INCOMING_QUEUE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(INCOMING_QUEUE_FILE, "w", encoding="utf-8") as f:
            f.truncate(0)
    except Exception:
        return

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            cid = item.get("cid", "manual")
            label = item.get("label", "Orb AI Assistant")
            text = item.get("text", "").strip()
            if text:
                with queue_lock:
                    if not any(q.get("text") == text for q in speech_queue):
                        speech_queue.append({
                            "cid": cid,
                            "label": label,
                            "text": text,
                            "queued_at": item.get("queued_at", time.time())
                        })
                        print(f"\n[AUTO-SPEAKER] 📥 External speech request queued: \"{text[:50]}...\" (queue depth: {len(speech_queue)})", flush=True)
        except Exception:
            pass


def speech_queue_worker():
    global last_spoken_cid
    print("[AUTO-SPEAKER] 🎧 Speech Queue Playback Worker Active (Unified Real-Time Orb Voice)...", flush=True)

    while True:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as sf:
                    sdata = json.load(sf)
                    if sdata.get("stop_requested", False):
                        with queue_lock:
                            if speech_queue:
                                speech_queue.clear()
                                print("\n[AUTO-SPEAKER] 🛑 Cleared speech queue on stop request.", flush=True)
                        if os.path.exists(INCOMING_QUEUE_FILE):
                            try:
                                with open(INCOMING_QUEUE_FILE, "w", encoding="utf-8") as f:
                                    f.truncate(0)
                            except Exception:
                                pass
                        update_live_state(is_speaking=False, current_text="", stop_requested=False)
            except Exception:
                pass

        # Check for externally enqueued speech requests
        check_incoming_queue_file()

        item = None
        with queue_lock:
            if speech_queue:
                item = speech_queue.popleft()

        if item is None:
            time.sleep(0.04)
            continue

        cid = item["cid"]
        label = item.get("label", "Orb AI Assistant")
        spoken_text = item["text"]

        # LIVE VOICE SELECT: Read live from voice_settings.json dynamically on every message
        live_settings = load_settings()
        if not live_settings.get("enabled", True):
            continue

        chat_cfg = load_chat_voices()
        announce_enabled = live_settings.get("announce_chat", chat_cfg.get("announce_chat", True))

        clean_label = label.strip()
        clean_label = re.sub(r'[\'\"’“”]+', '', clean_label).strip()

        if announce_enabled and clean_label and clean_label.lower() not in ("assistant", "agent"):
            spoken_text = f"From {clean_label}. {spoken_text}"

        voice = live_settings.get("voice", "en-GB-LibbyNeural")
        rate = live_settings.get("rate", "+0%")
        pitch = live_settings.get("pitch", "+0Hz")

        dev_idx, dev_name = get_active_output_device()
        safe_msg = spoken_text.encode("ascii", "ignore").decode("ascii")
        print(f"\n[AUTO-SPEAKER] ▶ Playing [{label}] with Live Orb Voice ({voice}): \"{safe_msg[:60]}\"...", flush=True)

        update_live_state(is_speaking=True, current_text=spoken_text, stop_requested=False, device_name=dev_name)
        log_history(spoken_text, f"{label} ({voice})")

        settings_override = {
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "volume": "+0%"
        }

        try:
            pcm = asyncio.run(synthesize_speech_pcm(spoken_text, settings_override))
            play_audio_pcm(pcm)
            last_spoken_cid = cid
        except Exception as e:
            print(f"[AUTO-SPEAKER] Playback error: {e}", flush=True)

        update_live_state(is_speaking=False, current_text="", stop_requested=False, device_name=dev_name)
        time.sleep(0.35)


def monitor_and_read():
    print(f"[AUTO-SPEAKER] Direct Hardware Multi-Chat Voice Engine Active (All Active Chats Monitored)...", flush=True)

    # Start playback worker thread
    worker_t = threading.Thread(target=speech_queue_worker, daemon=True)
    worker_t.start()

    SCAN_SIGNAL_FILE = os.path.join(BASE_DIR, "scan_all_chats.signal")

    def scan_transcripts():
        res = []
        try:
            _, active_path = get_active_chat_title_and_transcript()
            if active_path and os.path.exists(active_path):
                res.append(active_path)
            all_logs = glob.glob(os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl"))
            all_logs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for p in all_logs[:25]:
                if p not in res and os.path.exists(p):
                    res.append(p)
        except Exception:
            if os.path.exists(FALLBACK_LOG):
                res.append(FALLBACK_LOG)
        return res

    file_positions = {}
    seen_hashes = collections.deque(maxlen=400)

    def scan_for_missed_replies():
        print("[AUTO-SPEAKER] 🔍 Scanning all chats for missed replies while paused...", flush=True)
        all_files = scan_transcripts()
        missed_count = 0
        for p in all_files:
            if not os.path.exists(p):
                continue
            try:
                cur_sz = os.path.getsize(p)
                file_positions[p] = cur_sz
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for line in reversed(lines[-35:]):
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
                        msg_hash = hash(content[:150])
                        if msg_hash not in seen_hashes:
                            seen_hashes.append(msg_hash)
                            cid = p.split(os.sep)[-4]
                            queue_speech(cid, content, p)
                            missed_count += 1
                        break
            except Exception as e:
                pass
        print(f"[AUTO-SPEAKER] 🔍 Scan complete: queued {missed_count} missed replies.", flush=True)
        return missed_count

    # Initial seeding: set all existing transcript files to EOF so we only read new messages
    for p in scan_transcripts():
        try:
            sz = os.path.getsize(p)
            file_positions[p] = sz
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(max(0, sz - 5000))
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        if d.get("source") == "MODEL" and d.get("type") == "PLANNER_RESPONSE":
                            cnt = d.get("content", "").strip()
                            if cnt:
                                seen_hashes.append(hash(cnt[:150]))
                    except Exception:
                        pass
        except Exception:
            pass

    last_scan_time = time.time()
    known_files = list(file_positions.keys())
    print(f"[AUTO-SPEAKER] Tracking {len(known_files)} existing conversation threads simultaneously.", flush=True)

    was_paused = not load_settings().get("enabled", True)

    while True:
        try:
            is_enabled = load_settings().get("enabled", True)
            if was_paused and is_enabled:
                was_paused = False
                print("[AUTO-SPEAKER] 🔔 Unpaused! Running catch-up scan across all conversation threads...", flush=True)
                scan_for_missed_replies()
            elif not is_enabled:
                was_paused = True

            if os.path.exists(SCAN_SIGNAL_FILE):
                try:
                    os.remove(SCAN_SIGNAL_FILE)
                except Exception:
                    pass
                scan_for_missed_replies()

            now = time.time()
            if now - last_scan_time >= 2.0:
                last_scan_time = now
                all_files = scan_transcripts()
                for p in all_files:
                    if p not in file_positions:
                        file_positions[p] = os.path.getsize(p)
                known_files = all_files

            for p in known_files:
                if not os.path.exists(p):
                    continue
                try:
                    cur_size = os.path.getsize(p)
                except Exception:
                    continue

                prev_pos = file_positions.get(p, cur_size)
                if cur_size < prev_pos:
                    prev_pos = 0

                if cur_size > prev_pos:
                    try:
                        with open(p, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(prev_pos)
                            new_lines = f.readlines()
                            file_positions[p] = f.tell()

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
                                live_cfg = load_settings()
                                if not live_cfg.get("enabled", True):
                                    continue
                                msg_hash = hash(content[:150])
                                if msg_hash not in seen_hashes:
                                    seen_hashes.append(msg_hash)
                                    cid = p.split(os.sep)[-4]
                                    queue_speech(cid, content, p)
                    except Exception as e:
                        print(f"[AUTO-SPEAKER] Error reading {p}: {e}", flush=True)

        except Exception as e:
            print(f"[AUTO-SPEAKER] Loop exception: {e}", flush=True)

        time.sleep(0.04)


if __name__ == "__main__":
    monitor_and_read()
