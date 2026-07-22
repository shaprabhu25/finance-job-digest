"""Seed the company watchlist in bulk from the YC open dataset.

No scraping, no keys — a maintained JSON dataset of every YC company.
We filter to the relevant slice (actively hiring + India or remote) so the
watchlist starts full of quality companies, not all 6,000.

Run standalone to preview:  python3 seed_yc.py
Import seed_candidates() from the orchestrator to feed discovery/resolution.
"""
from __future__ import annotations

import json
import urllib.request
from typing import List, Dict

YC_ALL = "https://yc-oss.github.io/api/companies/all.json"
_UA = "Mozilla/5.0 (compatible; job-digest/1.0)"


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _india_or_remote(c: Dict) -> bool:
    regions = " ".join(c.get("regions") or []).lower()
    locs = (c.get("all_locations") or "").lower()
    return ("india" in regions or "india" in locs
            or "remote" in regions or "bengaluru" in locs or "bangalore" in locs)


def seed_candidates() -> List[Dict]:
    """Return the filtered YC company slice as {name, website, regions, ...}."""
    companies = _fetch(YC_ALL)
    out = []
    for c in companies:
        if not c.get("website"):
            continue
        if not c.get("isHiring"):
            continue
        if not _india_or_remote(c):
            continue
        out.append({
            "name": c.get("name"),
            "website": c.get("website"),
            "regions": c.get("regions") or [],
            "all_locations": c.get("all_locations") or "",
            "industry": c.get("industry"),
            "batch": c.get("batch"),
            "team_size": c.get("team_size"),
        })
    return out


if __name__ == "__main__":
    all_co = _fetch(YC_ALL)
    cands = seed_candidates()
    india = [c for c in cands if "india" in (" ".join(c["regions"]).lower() + c["all_locations"].lower())]
    print(f"YC total:            {len(all_co)}")
    print(f"hiring + india/remote: {len(cands)}   (of which India-tagged: {len(india)})")
    print("\nSample India-tagged candidates:")
    for c in india[:12]:
        print(f"  • {c['name']:22} {c['website']:34} {c['batch']:6} {c['industry']}")
