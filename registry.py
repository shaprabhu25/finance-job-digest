"""The company watchlist (companies.csv) — Box 1 of the system.

Filled by: the YC seeder (bulk), the friend's /add (one-off), never by hand-editing
required. Stores the RESOLVED ats_type+slug so we don't re-resolve every run.
"""
from __future__ import annotations

import csv
import os
from typing import Dict, List

from resolver import resolve

FIELDS = ["company_name", "ats_type", "slug_or_url", "careers_url", "active", "source", "added"]


def load_registry(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def save_registry(path: str, rows: List[Dict]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def _key(ats_type: str, slug: str) -> str:
    return f"{ats_type}:{slug}".lower()


def add_company(rows: List[Dict], name: str, careers_url: str, source: str,
                today: str, resolver_fn=None) -> Dict:
    """Resolve a careers URL to (ats_type, slug) and append if new.
    Returns {status: added|duplicate|unresolved, ...}. resolver_fn override lets
    the seeder pass discovery results; default uses the pure URL resolver."""
    ats_type, slug, conf = (resolver_fn(name, careers_url) if resolver_fn
                            else resolve(careers_url)[:3])
    if ats_type in (None, "scrape"):
        # keep it, but flag it needs a direct URL
        row = {"company_name": name, "ats_type": "scrape", "slug_or_url": careers_url,
               "careers_url": careers_url, "active": "no", "source": source, "added": today}
        rows.append(row)
        return {"status": "unresolved", "row": row}
    existing = {_key(r.get("ats_type", ""), r.get("slug_or_url", "")) for r in rows}
    if _key(ats_type, slug) in existing:
        return {"status": "duplicate", "ats": ats_type, "slug": slug}
    row = {"company_name": name, "ats_type": ats_type, "slug_or_url": slug,
           "careers_url": careers_url, "active": "yes", "source": source, "added": today}
    rows.append(row)
    return {"status": "added", "row": row}


def remove_company(rows: List[Dict], needle: str) -> int:
    n = needle.strip().lower()
    before = len(rows)
    kept = [r for r in rows if n not in r.get("company_name", "").lower()]
    rows[:] = kept
    return before - len(kept)


def active_companies(rows: List[Dict]) -> List[Dict]:
    return [r for r in rows if (r.get("active", "yes").lower() in ("yes", "true", "1"))
            and r.get("ats_type") and r.get("ats_type") != "scrape"]
