"""The dedupe state layer, backed by a JSONL file in the repo.

Everything the pipeline touches goes through this tiny interface:
    load_state -> partition -> (deliver new jobs) -> commit -> prune -> save_state

Swapping the backend later (Supabase, a Sheet) means reimplementing only
load_state/save_state; the pipeline never changes.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Dict, List, Tuple

from models import Job

PRUNE_DAYS = 60
Record = Dict[str, object]
State = Dict[str, Record]


def load_state(path: str) -> State:
    state: State = {}
    if not os.path.exists(path):
        return state
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            state[r["job_uid"]] = r
    return state


def save_state(path: str, state: State) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # sorted for deterministic, review-friendly git diffs
    with open(path, "w", encoding="utf-8") as f:
        for uid in sorted(state):
            f.write(json.dumps(state[uid], ensure_ascii=False) + "\n")


def partition(jobs: List[Job], state: State) -> Tuple[List[Job], List[Job], List[Job]]:
    """Split incoming jobs into (new, cross_board_dup, already_seen).

    Pure: does not mutate `state`. Also collapses duplicates *within* this batch
    (two identical postings in one run -> one 'new').
    """
    seen_uids = set(state)
    seen_hashes = {r["content_hash"] for r in state.values()}
    new: List[Job] = []
    dup: List[Job] = []
    reseen: List[Job] = []
    for job in jobs:
        if job.job_uid in seen_uids:
            reseen.append(job)
        elif job.content_hash in seen_hashes:
            dup.append(job)
        else:
            new.append(job)
            seen_uids.add(job.job_uid)      # collapse within-batch repeats
            seen_hashes.add(job.content_hash)
    return new, dup, reseen


def _record(job: Job, today: str, sent: bool, duplicate: bool = False) -> Record:
    return {
        "job_uid": job.job_uid,
        "content_hash": job.content_hash,
        "company": job.company,
        "title": job.title,
        "apply_url": job.apply_url,
        "source": job.source,
        "location_bucket": job.location_bucket,
        "first_seen": today,
        "last_seen": today,
        "sent": sent,
        "duplicate": duplicate,
    }


def commit(state: State, sent: List[Job], dup: List[Job], reseen: List[Job], today: str) -> State:
    """Fold a run's results back into state. Call AFTER delivery succeeds so a
    send failure doesn't mark a job as delivered."""
    for job in sent:
        state[job.job_uid] = _record(job, today, sent=True)
    for job in dup:                                   # remember so we don't re-eval it
        rec = state.get(job.job_uid) or _record(job, today, sent=False, duplicate=True)
        rec["last_seen"] = today
        state[job.job_uid] = rec
    for job in reseen:                                # keep-alive: refresh last_seen
        state[job.job_uid]["last_seen"] = today
    return state


def prune(state: State, today: str, days: int = PRUNE_DAYS) -> State:
    """Drop records not seen in `days`. A live job is re-seen every run so its
    last_seen stays current -> never pruned while open -> never resent."""
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    return {uid: r for uid, r in state.items() if str(r["last_seen"]) >= cutoff}
