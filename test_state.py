"""Proves the 5 'solid' acceptance criteria for the data layer.

Run: python3 test_state.py   (stdlib only, no pytest needed)
Simulates multiple 'days' by passing explicit ISO dates.
"""
from __future__ import annotations

import os
import tempfile

from models import Job
from state import load_state, save_state, partition, commit, prune

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


def run(jobs, state, today):
    """One full pipeline run without the delivery step."""
    new, dup, reseen = partition(jobs, state)
    state = commit(state, new, dup, reseen, today)   # pretend delivery of `new` succeeded
    state = prune(state, today)
    return new, state


# --- fixtures ---------------------------------------------------------------
def gh(id, title, loc="Bengaluru, India"):
    return Job("greenhouse", id, "Razorpay", title, loc,
               apply_url=f"https://boards.greenhouse.io/razorpay/jobs/{id}")

def rok(id, title, loc="Remote, India"):
    return Job("remoteok", id, "Razorpay", title, loc,
               apply_url=f"https://remoteok.com/l/{id}")


print("Criterion 1 — idempotent: a sent job is never sent again")
st = {}
new1, st = run([gh("100", "Manager, FP&A")], st, "2026-07-22")
new2, st = run([gh("100", "Manager, FP&A")], st, "2026-07-23")  # next day, same posting
check("day 1 sends it", [j.job_uid for j in new1] == ["greenhouse:100"])
check("day 2 sends nothing", new2 == [])

print("\nCriterion 2 — cross-board: same role on 2 boards -> one card")
st = {}
new1, st = run([gh("200", "Financial Controller")], st, "2026-07-22")
new2, st = run([rok("xy9", "Financial Controller")], st, "2026-07-23")  # reposted elsewhere
check("first board sends it", len(new1) == 1)
check("second board suppressed", new2 == [])

print("\nCriterion 2b — same run, both boards present at once")
st = {}
new, st = run([gh("201", "FP&A Manager"), rok("zz1", "FP&A Manager")], st, "2026-07-22")
check("only one of the two delivered", len(new) == 1)

print("\nCriterion 3 — a genuinely new role is always caught")
st = {}
_, st = run([gh("300", "Manager, FP&A")], st, "2026-07-22")
new, st = run([gh("300", "Manager, FP&A"), gh("301", "Finance Business Partner")], st, "2026-07-23")
check("new req 301 delivered, old 300 not", [j.source_job_id for j in new] == ["301"])

print("\nCriterion 4 — prune by last_seen, and reopened-after-prune resends")
st = {}
# Day A: job open
_, st = run([gh("400", "Treasury Lead")], st, "2026-01-01")
# It stays open and is re-seen 30 days later -> must NOT be pruned, must NOT resend
new_mid, st = run([gh("400", "Treasury Lead")], st, "2026-01-31")
check("still-open job not resent at day 30", new_mid == [])
check("still-open job survives prune", "greenhouse:400" in st)
# It disappears from feeds. The daily cron keeps running on OTHER jobs and
# keeps pruning; after 60 days absent it ages out of state.
_, st = run([], st, "2026-04-15")
check("aged out of state after 60d gone", "greenhouse:400" not in st)
# Now it reopens -> treated as new again
new_reopen, st = run([gh("400", "Treasury Lead")], st, "2026-05-01")
check("job gone >60d then reopened -> resent", len(new_reopen) == 1)

print("\nCriterion 5 — state survives a save/load round-trip (persistence)")
st = {}
_, st = run([gh("500", "Head of Finance"), gh("501", "Senior Accountant")], st, "2026-07-22")
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "state", "seen.jsonl")
    save_state(path, st)
    reloaded = load_state(path)
    check("round-trip preserves all records", set(reloaded) == set(st))
    # after reload, the same jobs must still be recognised as seen (not resent)
    new_after, _ = run([gh("500", "Head of Finance")], reloaded, "2026-07-23")
    check("reloaded state still dedupes", new_after == [])

print(f"\n{'='*48}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for n in FAIL:
        print("  FAILED:", n)
    raise SystemExit(1)
print("Data layer is SOLID ✓")
