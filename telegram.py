"""Telegram delivery + command intake. No server: send via HTTP, read commands
via getUpdates once per run (fits the cron model).

The bot token / chat id are read from env (GitHub Secrets) — never hardcoded.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from models import Job

_API = "https://api.telegram.org/bot{token}/{method}"


def _call(token: str, method: str, params: dict) -> dict:
    url = _API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_BUCKET_LABEL = {
    "bengaluru": "Bengaluru", "remote_india": "Remote · India",
    "remote_ww": "Remote · Worldwide", "remote_unspecified": "Remote",
}


def format_card(job: Job) -> str:
    """One job -> an HTML Telegram card. Only shows fields we actually have."""
    loc = _BUCKET_LABEL.get(job.location_bucket, job.location_raw or "—")
    lines = [
        f"💼 <b>{_esc(job.title)}</b>",
        f"🏢 {_esc(job.company)}  ·  📍 {_esc(loc)}",
        f"🧑 Experience: {_esc(job.yoe) if job.yoe else 'not specified'}",
        f"💰 Salary: {_esc(job.salary) if job.salary else 'not listed'}",
    ]
    if job.posted_at:
        lines.append(f"🗓️ Posted: {_esc(job.posted_at)}  ·  via {job.source}")
    else:
        lines.append(f"🔎 via {job.source}")
    lines.append(f'🔗 <a href="{_esc(job.apply_url)}">Apply</a>')
    return "\n".join(lines)


def send_message(token: str, chat_id: str, text: str, disable_preview: bool = True) -> dict:
    return _call(token, "sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true" if disable_preview else "false",
    })


def send_cards(token: str, chat_id: str, jobs: List[Job], cap: int = 40,
               pace: float = 1.1) -> int:
    """Send up to `cap` cards, paced to stay well under rate limits."""
    sent = 0
    for job in jobs[:cap]:
        try:
            send_message(token, chat_id, format_card(job))
            sent += 1
            time.sleep(pace)
        except Exception as e:
            print(f"  ! telegram send failed: {e}")
    if len(jobs) > cap:
        send_message(token, chat_id, f"…and <b>{len(jobs) - cap}</b> more today "
                                     f"(capped at {cap} to keep it skimmable).")
    return sent


def get_updates(token: str, offset: Optional[int]) -> List[Dict]:
    params = {"timeout": "0"}
    if offset is not None:
        params["offset"] = str(offset)
    try:
        r = _call(token, "getUpdates", params)
        return r.get("result", []) if r.get("ok") else []
    except Exception as e:
        print(f"  ! getUpdates failed: {e}")
        return []


# --- offset persistence so we don't reprocess the same commands -------------
def load_offset(path: str) -> Optional[int]:
    if os.path.exists(path):
        try:
            return int(open(path).read().strip())
        except Exception:
            return None
    return None


def save_offset(path: str, offset: int) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    open(path, "w").write(str(offset))
