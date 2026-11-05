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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_blob_token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if token:
        return token
    for fname in [".env.local", ".env"]:
        p = os.path.join(BASE_DIR, fname)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
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

def get_cloud_sync_state():
    token = get_blob_token()
    if not token:
        return None
    try:
        req = urllib.request.Request(
            "https://blob.vercel-storage.com/?prefix=orb_sync_state",
            method="GET"
        )
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("x-api-version", "7")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            blobs = data.get("blobs", [])
            if not blobs:
                return None
            blobs.sort(key=lambda b: b.get("uploadedAt", ""), reverse=True)
            latest_url = blobs[0].get("url")
            with urllib.request.urlopen(latest_url, timeout=8) as content_resp:
                return json.loads(content_resp.read().decode("utf-8"))
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
        state_data["updated_at"] = int(time.time() * 1000)
        body = json.dumps(state_data).encode("utf-8")
        req = urllib.request.Request(
            "https://blob.vercel-storage.com/orb_sync_state.json",
            data=body,
            method="PUT"
        )
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("x-api-version", "7")
        req.add_header("Content-Type", "application/json")
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

    # 1. Focus Tasks: Key by id
    existing_tasks = {t["id"]: t for t in existing.get("focus_tasks", []) if isinstance(t, dict) and "id" in t}
    incoming_tasks = {t["id"]: t for t in incoming.get("focus_tasks", []) if isinstance(t, dict) and "id" in t}
    
    # Update or add incoming tasks
    for tid, t in incoming_tasks.items():
        if tid in existing_tasks:
            # Merge fields, favoring incoming if modified
            existing_tasks[tid].update(t)
        else:
            existing_tasks[tid] = t

    merged["focus_tasks"] = list(existing_tasks.values())
    
    # 2. Assistant Tasks: Key by id
    existing_ast = {t["id"]: t for t in existing.get("assistant_tasks", []) if isinstance(t, dict) and "id" in t}
    incoming_ast = {t["id"]: t for t in incoming.get("assistant_tasks", []) if isinstance(t, dict) and "id" in t}
    for tid, t in incoming_ast.items():
        if tid in existing_ast:
            existing_ast[tid].update(t)
        else:
            existing_ast[tid] = t
    merged["assistant_tasks"] = list(existing_ast.values())

    # 3. Categories: Key by id
    existing_cats = {c["id"]: c for c in existing.get("categories", []) if isinstance(c, dict) and "id" in c}
    incoming_cats = {c["id"]: c for c in incoming.get("categories", []) if isinstance(c, dict) and "id" in c}
    existing_cats.update(incoming_cats)
    if existing_cats:
        merged["categories"] = list(existing_cats.values())

    # 4. Messages / Conversation: Dedup by (text, time)
    msg_seen = set()
    combined_msgs = []
    for msg in existing.get("messages", []) + incoming.get("messages", []):
        if isinstance(msg, dict):
            key = (msg.get("text", "").strip(), msg.get("time", "").strip(), msg.get("role", "").strip())
            if key not in msg_seen:
                msg_seen.add(key)
                combined_msgs.append(msg)
    # Limit to latest 100 messages
    merged["messages"] = combined_msgs[-100:]

    # 5. Scalar pointers
    for k in ["active_category_id", "active_focus_task_id", "voice", "midday_call_active"]:
        if k in incoming and incoming[k] is not None:
            merged[k] = incoming[k]

    # 6. Google Workspace items
    if incoming.get("calendar_events"):
        merged["calendar_events"] = incoming["calendar_events"]
    if incoming.get("created_docs"):
        merged["created_docs"] = incoming["created_docs"]

    merged["updated_at"] = int(time.time() * 1000)
    return merged
