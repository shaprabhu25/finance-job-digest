"""Orchestrator — one daily run. Ties every module together.

  registry -> (telegram commands) -> fetch -> filter -> dedupe -> deliver -> commit

DRY_RUN=1 prints cards instead of sending, and skips Telegram polling, so the
whole pipeline is testable with no bot token.
"""
from __future__ import annotations

import os
import re
from datetime import date

from registry import load_registry, save_registry, add_company, remove_company, active_companies
from fetchers import fetch_company, fetch_remoteok
from filters import passes
from state import load_state, save_state, partition, commit, prune
import telegram as tg

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES = os.path.join(HERE, "companies.csv")
SEEN = os.path.join(HERE, "state", "seen.jsonl")
OFFSET = os.path.join(HERE, "state", "tg_offset.txt")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1" or not (TOKEN and CHAT)
DAILY_CAP = int(os.environ.get("DAILY_CAP", "40"))

HELP = ("👋 Commands:\n"
        "/add [careers URL] — watch a company\n"
        "/list — show the watchlist\n"
        "/remove [name] — stop watching\n"
        "/suggest — recently-funded companies to consider")


def _h(s) -> str:
    """Escape text going into an HTML Telegram message (names, etc.)."""
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _name_from_url(url: str) -> str:
    m = re.search(r"(?:greenhouse\.io|lever\.co|ashbyhq\.com)/([a-z0-9_-]+)", url, re.I)
    if m:
        return m.group(1).replace("-", " ").title()
    m = re.search(r"https?://(?:www\.)?([a-z0-9-]+)\.", url, re.I)
    return m.group(1).title() if m else url


def handle_commands(rows, today) -> bool:
    """Process /add /list /remove /suggest. Returns True if registry changed."""
    offset = tg.load_offset(OFFSET)
    updates = tg.get_updates(TOKEN, offset)
    changed = False
    last_id = offset
    for u in updates:
        last_id = u.get("update_id")
        # Per-update guard: one bad message must never crash the whole digest,
        # and the offset still advances so it isn't reprocessed forever.
        try:
            msg = u.get("message") or u.get("channel_post") or {}
            text = (msg.get("text") or "").strip()
            chat_id = str((msg.get("chat") or {}).get("id", CHAT))
            if not text:
                continue
            cmd, _, arg = text.partition(" ")
            cmd, arg = cmd.lower(), arg.strip()
            if cmd == "/add" and arg:
                res = add_company(rows, _name_from_url(arg), arg, "telegram", today)
                changed = True
                if res["status"] == "added":
                    r = res["row"]
                    tg.send_message(TOKEN, chat_id, f"✓ Watching <b>{_h(r['company_name'])}</b> ({_h(r['ats_type'])})")
                elif res["status"] == "duplicate":
                    tg.send_message(TOKEN, chat_id, "Already on the list.")
                else:
                    tg.send_message(TOKEN, chat_id, "Added, but couldn't auto-detect the ATS — paste the direct board URL (Greenhouse/Lever/Ashby) if you have it.")
            elif cmd == "/remove" and arg:
                n = remove_company(rows, arg); changed = changed or n > 0
                tg.send_message(TOKEN, chat_id, f"Removed {n} entr{'y' if n == 1 else 'ies'}.")
            elif cmd == "/list":
                act = active_companies(rows)
                body = "\n".join(f"• {_h(r['company_name'])} ({_h(r['ats_type'])})" for r in act[:80]) or "empty"
                tg.send_message(TOKEN, chat_id, f"<b>Watching {len(act)}:</b>\n{body}")
            elif cmd == "/suggest":
                from funding import funding_candidates
                c = funding_candidates()
                body = "\n".join(f"• {_h(x['company'])}" for x in c[:15]) or "none found"
                tg.send_message(TOKEN, chat_id, f"<b>Recently funded — /add any:</b>\n{body}")
            elif cmd in ("/start", "/help"):
                tg.send_message(TOKEN, chat_id, HELP)
        except Exception as e:
            print(f"  ! command failed on update {last_id}: {e}")
    if last_id is not None and updates:
        tg.save_offset(OFFSET, last_id + 1)
    return changed


def run():
    today = date.today().isoformat()
    rows = load_registry(COMPANIES)

    if not DRY_RUN:
        if handle_commands(rows, today):
            save_registry(COMPANIES, rows)

    companies = active_companies(rows)
    print(f"Fetching {len(companies)} companies + aggregators…")
    jobs = []
    for r in companies:
        jobs += fetch_company(r["ats_type"], r["slug_or_url"], r["company_name"])
    try:
        jobs += fetch_remoteok()
    except Exception as e:
        print(f"  ! remoteok: {e}")

    kept = [j for j in jobs if passes(j)]
    print(f"Fetched {len(jobs)} jobs → {len(kept)} pass filters")

    state = load_state(SEEN)
    new, dup, reseen = partition(kept, state)
    print(f"New: {len(new)} · cross-board dup: {len(dup)} · already-seen: {len(reseen)}")

    # Heartbeat: on a quiet day still say something, so silence never reads as
    # "it's broken". Only sent when there were genuinely no new roles.
    quiet_msg = (f"✅ Checked {len(companies)} companies · "
                 f"no new finance roles today.")

    if DRY_RUN:
        for j in new[:DAILY_CAP]:
            print("\n" + tg.format_card(j))
        if new:
            print(f"\n[DRY_RUN] would send {min(len(new), DAILY_CAP)} card(s)")
        else:
            print(f"\n[DRY_RUN] would send heartbeat: {quiet_msg}")
    elif new:
        n = tg.send_cards(TOKEN, CHAT, new, cap=DAILY_CAP)
        print(f"Sent {n} card(s)")
    else:
        try:
            tg.send_message(TOKEN, CHAT, quiet_msg)
            print("No new jobs — heartbeat sent.")
        except Exception as e:
            print(f"  ! heartbeat failed: {e}")

    commit(state, new, dup, reseen, today)
    state = prune(state, today)
    save_state(SEEN, state)
    print("State committed.")


if __name__ == "__main__":
    run()
