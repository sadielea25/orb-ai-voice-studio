"""
sync_engine.py
Centralized Cloud State Synchronization for Orb AI Voice Studio.
Syncs Focus Tasks, To-Dos, Categories, Conversation History, and Google Workspace items
seamlessly across Desktop (PC / Electron / Browser) and Android Native Thin Client (Option B).
"""

import os
import json
import time
import urllib.request
import urllib.error
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_blob_token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if token:
        return token
    for d in [BASE_DIR, os.path.dirname(BASE_DIR)]:
        for fname in [".env.local", ".env"]:
            p_file = os.path.join(d, fname)
            if os.path.exists(p_file):
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("BLOB_READ_WRITE_TOKEN="):
                                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if token:
                                    os.environ["BLOB_READ_WRITE_TOKEN"] = token
                                    return token
                except Exception:
                    pass
    return ""

def fetch_json_url(url, timeout=8):
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*"
    }
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    try:
        curl_bin = "curl.exe" if os.name == "nt" else "curl"
        res = subprocess.run([curl_bin, "-s", "--max-time", str(timeout), url], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None

def get_cloud_sync_state():
    token = get_blob_token()
    if not token:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-version": "7",
            "User-Agent": BROWSER_UA
        }
        data = None
        try:
            import requests
            resp = requests.get("https://blob.vercel-storage.com/?prefix=orb_sync_state", headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
        except Exception:
            pass
        if not data:
            req = urllib.request.Request("https://blob.vercel-storage.com/?prefix=orb_sync_state", method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        blobs = data.get("blobs", []) if data else []
        if not blobs:
            return None
        blobs.sort(key=lambda b: b.get("uploadedAt", ""), reverse=True)
        latest_url = blobs[0].get("url")
        content = fetch_json_url(latest_url, timeout=8)
        return content
    except Exception as e:
        print(f"[SYNC-ENGINE-GET-ERR]: {e}", flush=True)
        return None

def save_cloud_sync_state(state_data):
    token = get_blob_token()
    if not token:
        return None
    try:
        if not isinstance(state_data, dict):
            state_data = {}
        if "updated_at" not in state_data or not state_data["updated_at"]:
            state_data["updated_at"] = int(time.time() * 1000)
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-version": "7",
            "Content-Type": "application/json",
            "User-Agent": BROWSER_UA
        }
        try:
            import requests
            resp = requests.put("https://blob.vercel-storage.com/orb_sync_state.json", json=state_data, headers=headers, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json().get("url")
        except Exception:
            pass
        body = json.dumps(state_data).encode("utf-8")
        req = urllib.request.Request("https://blob.vercel-storage.com/orb_sync_state.json", data=body, method="PUT", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("url")
    except Exception as e:
        print(f"[SYNC-ENGINE-PUT-ERR]: {e}", flush=True)
        return None

def merge_sync_states(existing, incoming):
    if not existing:
        return incoming or {}
    if not incoming:
        return existing or {}

    merged = dict(existing)

    # 1. Focus Tasks
    if "focus_tasks" in incoming and isinstance(incoming["focus_tasks"], list):
        merged["focus_tasks"] = incoming["focus_tasks"]

    # 2. Assistant Tasks
    if "assistant_tasks" in incoming and isinstance(incoming["assistant_tasks"], list):
        merged["assistant_tasks"] = incoming["assistant_tasks"]

    # 3. Categories
    if "categories" in incoming and isinstance(incoming["categories"], list) and len(incoming["categories"]) > 0:
        merged["categories"] = incoming["categories"]

    # 4. Messages / Conversation: Dedup by (text, time, role)
    msg_seen = set()
    combined_msgs = []
    for msg in existing.get("messages", []) + incoming.get("messages", []):
        if isinstance(msg, dict):
            key = (msg.get("text", "").strip(), msg.get("time", "").strip(), msg.get("role", "").strip())
            if key not in msg_seen:
                msg_seen.add(key)
                combined_msgs.append(msg)
    merged["messages"] = combined_msgs[-100:]

    # 5. Scalar pointers
    for k in ["active_category_id", "active_focus_task_id", "voice", "midday_call_active"]:
        if k in incoming and incoming[k] is not None:
            merged[k] = incoming[k]

    # 6. Planning state
    if "planning" in incoming and isinstance(incoming["planning"], dict):
        merged["planning"] = incoming["planning"]

    # 7. Google Workspace items
    if "calendar_events" in incoming and isinstance(incoming["calendar_events"], list):
        merged["calendar_events"] = incoming["calendar_events"]
    if "created_docs" in incoming and isinstance(incoming["created_docs"], list):
        merged["created_docs"] = incoming["created_docs"]

    # 8. Antigravity Cloud Bridge items
    if "pending_antigrav_prompts" in incoming and isinstance(incoming["pending_antigrav_prompts"], list):
        merged["pending_antigrav_prompts"] = incoming["pending_antigrav_prompts"]
    if "active_chat_title" in incoming and incoming["active_chat_title"]:
        merged["active_chat_title"] = incoming["active_chat_title"]
    if "projects" in incoming and isinstance(incoming["projects"], list):
        merged["projects"] = incoming["projects"]
    if "scan_requested" in incoming:
        merged["scan_requested"] = incoming["scan_requested"]
    if "app_version" in incoming:
        merged["app_version"] = incoming["app_version"]

    # 9. Packing Lists & Match Day Budgeting
    if "packing_items" in incoming and isinstance(incoming["packing_items"], list):
        merged["packing_items"] = incoming["packing_items"]
    if "packing_categories" in incoming and isinstance(incoming["packing_categories"], list) and len(incoming["packing_categories"]) > 0:
        merged["packing_categories"] = incoming["packing_categories"]
    if "budget_items" in incoming and isinstance(incoming["budget_items"], list):
        merged["budget_items"] = incoming["budget_items"]
    if "budget_calculator" in incoming and isinstance(incoming["budget_calculator"], dict):
        merged["budget_calculator"] = incoming["budget_calculator"]
    if "live_patches" in incoming and isinstance(incoming["live_patches"], list):
        merged["live_patches"] = incoming["live_patches"]
    if "notion_projects" in incoming and isinstance(incoming["notion_projects"], list):
        merged["notion_projects"] = incoming["notion_projects"]

    merged["updated_at"] = incoming.get("updated_at") or int(time.time() * 1000)
    return merged
