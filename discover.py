"""Turn a company website into a monitorable (ats_type, slug) automatically.

This is the seed->monitor bridge: given razorpay.com, find the careers page and
detect which ATS backs it. Best-effort by nature; whatever can't resolve is
returned as ('scrape', ...) and flagged for a manual careers URL.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import List, Optional, Tuple

from resolver import detect_from_page, resolve

_UA = "Mozilla/5.0 (compatible; job-digest/1.0)"
_CAREERS_LINK = re.compile(
    r'href=["\']([^"\']*(?:careers?|/jobs|join-us|work-with-us|hiring|life-at)[^"\']*)["\']', re.I)

Discovery = Tuple[Optional[str], Optional[str], Optional[str], str]  # ats, slug, careers_url, confidence


def _get(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def slug_candidates(name: str) -> List[str]:
    """Company name -> plausible ATS board slugs, most-likely first."""
    low = (name or "").lower()
    full = re.sub(r"[^a-z0-9]", "", low)
    first = re.sub(r"[^a-z0-9]", "", low.split()[0]) if low.split() else ""
    # drop generic suffixes for the "first meaningful token" guess
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", low).split()
             if w not in ("inc", "labs", "group", "technologies", "payments", "the")]
    lead = re.sub(r"[^a-z0-9]", "", words[0]) if words else ""
    out = []
    for s in (full, lead, first):
        if s and len(s) >= 3 and s not in out:
            out.append(s)
    return out


def probe_ats_by_name(name: str) -> Discovery:
    """Guess the board slug from the name and confirm against the live ATS API.
    A hit on boards-api.greenhouse.io/<slug> etc. is company-specific, so this is
    reliable — and it catches custom careers UIs that HTML scraping misses."""
    for slug in slug_candidates(name):
        # greenhouse
        try:
            d = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            if d.get("jobs"):
                return ("greenhouse", slug, None, "slug-probe")
        except Exception:
            pass
        # lever
        try:
            d = _get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1")
            if isinstance(d, list) and d:
                return ("lever", slug, None, "slug-probe")
        except Exception:
            pass
        # ashby
        try:
            d = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if d.get("jobs"):
                return ("ashby", slug, None, "slug-probe")
        except Exception:
            pass
    return ("scrape", None, None, "scrape")


def discover_ats(website: str, name: str = "") -> Discovery:
    # 0. cheapest + most reliable: guess the slug from the name, confirm via API.
    if name:
        hit = probe_ats_by_name(name)
        if hit[0] not in ("scrape", None):
            return hit

    site = (website or "").strip().rstrip("/")
    if not site:
        return (None, None, None, "empty")
    if not site.startswith("http"):
        site = "https://" + site
    try:
        home = _get(site)
    except Exception as e:
        return (None, None, None, f"unreachable:{type(e).__name__}")

    # 1. board embedded right on the homepage?
    ats, slug, conf = detect_from_page(home)
    if ats != "scrape":
        return (ats, slug, site, conf)

    # 2. follow the first careers/jobs link
    for m in _CAREERS_LINK.finditer(home):
        href = m.group(1)
        url = href if href.startswith("http") else site + "/" + href.lstrip("/")
        r = resolve(url)                         # the careers link may BE a board url
        if r[0] in ("greenhouse", "lever", "ashby", "workday"):
            return (r[0], r[1], url, "careers-link")
        try:
            page = _get(url)
        except Exception:
            continue
        ats, slug, conf = detect_from_page(page)
        if ats != "scrape":
            return (ats, slug, url, conf)
        break                                    # try only the first careers link (speed)

    # 3. guess common paths
    for path in ("/careers", "/jobs", "/careers/"):
        try:
            page = _get(site + path)
        except Exception:
            continue
        ats, slug, conf = detect_from_page(page)
        if ats != "scrape":
            return (ats, slug, site + path, conf)

    return ("scrape", None, site, "scrape")


if __name__ == "__main__":
    from seed_yc import seed_candidates
    sample = seed_candidates()[:14]
    resolved = 0
    print(f"Resolving ATS for {len(sample)} real YC companies (live):\n")
    for c in sample:
        ats, slug, url, conf = discover_ats(c["website"], c["name"])
        ok = ats and ats not in ("scrape", None)
        resolved += 1 if ok else 0
        tag = f"{ats}:{slug}" if ok else (ats or conf)
        print(f"  {'OK ' if ok else '-- '} {c['name']:20} -> {tag:28} ({conf})")
    print(f"\nAuto-resolved {resolved}/{len(sample)} = {round(100*resolved/len(sample))}% "
          f"(rest get flagged for a manual careers URL)")
