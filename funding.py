"""Phase-2 lead feeder: recently-funded Indian companies -> /suggest candidates.

Reads funding-news RSS, extracts the company name from the headline, and returns
candidates. This is intentionally ASSISTIVE, not autonomous: the extraction is
fuzzy (headlines vary), so output is surfaced to the user to confirm with /add,
never auto-added. Point FEEDS at funding-category feeds for higher signal.
"""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

_UA = "Mozilla/5.0 (compatible; job-digest/1.0)"

# Prefer funding-specific category feeds; general feeds work but are noisier.
FEEDS = [
    "https://inc42.com/tag/funding/feed/",
    "https://yourstory.com/category/funding/feed",
    "https://inc42.com/feed/",
]

# "X raises ₹Y", "X bags $Y", "X secures", "X closes round"
_FUND = re.compile(r"^(.*?)\s+(raises|bags|secures|closes|nets|mops up|raise|raised)\b", re.I)
_MONEY = re.compile(r"(₹|rs\.?|\$|inr)\s*[\d,.]+\s*(cr|crore|mn|million|bn|billion|lakh|k)?", re.I)


def _companyish(name: str) -> str:
    name = re.sub(r"^(exclusive|breaking|watch)[:\-]\s*", "", name.strip(), flags=re.I)
    # drop leading descriptors: "Fintech Startup X", "Wealthtech Startup X"
    name = re.sub(r"^\w+tech\s+startup\s+", "", name, flags=re.I)
    name = re.sub(r"^\w+\s+startup\s+", "", name, flags=re.I)
    return name.strip()


def funding_candidates(limit_per_feed: int = 40) -> List[Dict]:
    out, seen = [], set()
    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": _UA})
            raw = urllib.request.urlopen(req, timeout=20).read()
            items = ET.fromstring(raw).findall(".//item")
        except Exception:
            continue
        for it in items[:limit_per_feed]:
            title = (it.findtext("title") or "").strip()
            m = _FUND.search(title)
            if not m or not _MONEY.search(title):     # require a money mention -> real funding
                continue
            company = _companyish(m.group(1))
            key = company.lower()
            if not company or key in seen or len(company) < 2:
                continue
            seen.add(key)
            out.append({"company": company, "headline": title,
                        "link": it.findtext("link") or ""})
    return out


if __name__ == "__main__":
    cands = funding_candidates()
    print(f"Funding candidates found: {len(cands)}\n")
    for c in cands[:15]:
        print(f"  • {c['company']:28} <= {c['headline'][:64]}")
