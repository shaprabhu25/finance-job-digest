"""Turn a pasted careers URL into (ats_type, slug) automatically.

The friend never types "greenhouse" or a slug. He pastes ONE thing — the URL
of a company's careers page — and this resolves it. Two stages:

  1. resolve(url)         -> pure, offline. Handles the ~80% case where the URL
                            is already a direct ATS board (boards.greenhouse.io/x, ...).
  2. detect_from_page(html) -> pure, offline given html. Handles company-own-domain
                            pages (razorpay.com/careers) that EMBED a board; the
                            fetch layer downloads the html and calls this.

Anything unresolved falls back to ("scrape", url) and is reported back to him in
the digest footer so he can fix it — no silent failure.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

Resolution = Tuple[Optional[str], Optional[str], str]  # (ats_type, slug_or_url, confidence)

# Direct ATS board URLs -> (ats_type, regex capturing the slug)
_DIRECT = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"boards\.eu\.greenhouse\.io/([a-z0-9_-]+)", re.I)),
    ("lever",      re.compile(r"jobs\.(?:eu\.)?lever\.co/([a-z0-9_-]+)", re.I)),
    ("ashby",      re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([a-z0-9_-]+)", re.I)),
    ("workable",   re.compile(r"(?:apply|jobs)\.workable\.com/([a-z0-9_-]+)", re.I)),
    ("recruitee",  re.compile(r"([a-z0-9-]+)\.recruitee\.com", re.I)),
]
_WORKDAY = re.compile(r"[a-z0-9-]+\.myworkdayjobs\.com/[^\s?#]+", re.I)


def resolve(url_or_slug: str) -> Resolution:
    s = (url_or_slug or "").strip()
    if not s:
        return (None, None, "empty")
    for ats, rx in _DIRECT:
        m = rx.search(s)
        if m:
            return (ats, m.group(1), "exact")
    if _WORKDAY.search(s):
        full = s if s.lower().startswith("http") else "https://" + s
        return ("workday", full, "exact")     # Workday's identifier is its full path
    if "://" in s or "." in s:
        return ("scrape", s, "scrape")        # a real URL, just not a known ATS host
    return (None, None, "unknown")            # bare token, can't classify -> ask for a URL


# Fingerprints of a board EMBEDDED inside a company's own careers page.
_EMBED = [
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I)),
    ("lever",      re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I)),
    ("ashby",      re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"careers\.smartrecruiters\.com/([a-z0-9_-]+)", re.I)),
]


def detect_from_page(html: str) -> Resolution:
    """Given the HTML of a company careers page, find an embedded ATS board."""
    for ats, rx in _EMBED:
        m = rx.search(html or "")
        if m:
            return (ats, m.group(1), "embedded")
    return ("scrape", None, "scrape")
