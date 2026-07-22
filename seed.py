"""Bulk-seed companies.csv from the YC dataset. Run once (or re-run to top up).

For each YC candidate: auto-discover its ATS, add to the registry. Re-running is
safe — companies already in the registry are skipped without re-resolving.
Set SEED_LIMIT to cap how many to process per run (default 250).
"""
from __future__ import annotations

import os
from datetime import date

from seed_yc import seed_candidates
from discover import discover_ats
from registry import load_registry, save_registry, add_company

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES = os.path.join(HERE, "companies.csv")
LIMIT = int(os.environ.get("SEED_LIMIT", "250"))


def _resolver(name, website):
    ats, slug, _url, conf = discover_ats(website, name)
    return (ats, slug, conf)


def run():
    today = date.today().isoformat()
    rows = load_registry(COMPANIES)
    have = {r.get("company_name", "").lower() for r in rows}

    cands = [c for c in seed_candidates() if c["name"].lower() not in have][:LIMIT]
    print(f"Seeding up to {len(cands)} new YC companies (of {len(seed_candidates())} total)…")

    added = resolved = 0
    for i, c in enumerate(cands, 1):
        res = add_company(rows, c["name"], c["website"], "yc-seed", today, resolver_fn=_resolver)
        if res["status"] == "added":
            added += 1
            resolved += 1
        if i % 25 == 0:
            print(f"  …{i}/{len(cands)}  (added {added})")
            save_registry(COMPANIES, rows)   # checkpoint so a timeout keeps progress

    save_registry(COMPANIES, rows)
    print(f"Done. Newly monitored: {resolved}. Registry now has {len(rows)} rows.")


if __name__ == "__main__":
    run()
