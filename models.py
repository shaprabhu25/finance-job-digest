"""Normalized job model + the two dedupe keys.

Every source (Greenhouse, Lever, Workday, HN, RemoteOK, scraped pages) gets
mapped into a single `Job`. Downstream code (filter, dedupe, delivery) never
knows or cares where a job came from. This is what makes dedupe "cross-board".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """lowercase, strip punctuation, collapse whitespace -> stable token string."""
    if not text:
        return ""
    return _NON_ALNUM.sub(" ", text.lower()).strip()


# Remote roles that name one of these are restricted to a region he can't take.
_FOREIGN = (
    "united states", "usa", "u.s.", "(us", " us)", "us only", "us-based", "americas",
    "united kingdom", " uk", "emea", "europe", "european", "canada", "australia",
    "singapore", "germany", "ireland", "france", "netherlands", "poland", "brazil",
    "latam", "philippines", "mexico", "apac", "new york", "london", "california",
)


def bucket_location(location_raw: str) -> str:
    """Coarse, deterministic location bucket used inside the content hash AND by
    the location filter.

    Buckets:
      bengaluru          -> on-site/hybrid/remote Bangalore  (accept)
      remote_india       -> remote, India named             (accept)
      remote_ww          -> remote, worldwide/global/anywhere (accept)
      remote_unspecified -> remote, no region named          (accept, inflate luck)
      remote_other       -> remote, but a foreign region named (reject)
      other              -> on-site somewhere that isn't Bangalore (reject)
    """
    l = " " + (location_raw or "").lower() + " "
    is_remote = any(k in l for k in ("remote", "anywhere", "work from home", "wfh", "distributed"))
    in_blr = any(k in l for k in ("bengaluru", "bangalore", "bangaluru"))
    in_india = in_blr or "india" in l
    worldwide = any(k in l for k in ("worldwide", "global", "anywhere", "any location", "any where"))

    if in_blr:
        return "bengaluru"
    if is_remote:
        if in_india:
            return "remote_india"
        if worldwide:
            return "remote_ww"
        if any(k in l for k in _FOREIGN):
            return "remote_other"
        return "remote_unspecified"
    if in_india:
        return "other"        # on-site elsewhere in India (Mumbai, Delhi...) -> not his target
    return "other"


# Region is coarser than bucket: it's what the content hash uses so the SAME
# role listed as "Bengaluru, India" on one board and "Remote, India" on another
# still collapses to one card. Worldwide/unspecified remote share a region so a
# role listed "Remote" vs "Remote worldwide" also collapses.
_REGION = {
    "bengaluru": "india",
    "remote_india": "india",
    "remote_ww": "remote_ww",
    "remote_unspecified": "remote_ww",
    "remote_other": "other",
    "other": "other",
}


@dataclass
class Job:
    source: str            # "greenhouse" | "lever" | "workday" | "hn" | "remoteok" | "scrape" | ...
    source_job_id: str     # native id from the source ("" for scraped pages)
    company: str
    title: str
    location_raw: str = ""
    apply_url: str = ""
    posted_at: Optional[str] = None   # ISO date or None
    yoe: Optional[str] = None         # extracted display, e.g. "5+ yrs"; nullable
    yoe_min: Optional[int] = None     # extracted min years, drives the level filter
    salary: Optional[str] = None      # extracted later, nullable
    description: str = ""             # used for extraction, not persisted

    @property
    def location_bucket(self) -> str:
        return bucket_location(self.location_raw)

    @property
    def region(self) -> str:
        return _REGION[self.location_bucket]

    @property
    def job_uid(self) -> str:
        """Layer 1 key: stable native id -> perfect same-source dedupe.

        Falls back to a hash of the apply URL (or content) for scraped pages
        that have no native id.
        """
        nid = str(self.source_job_id).strip()
        if nid:
            return f"{self.source}:{nid}"
        basis = self.apply_url or f"{self.company}|{self.title}|{self.location_bucket}"
        return f"{self.source}:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def content_hash(self) -> str:
        """Layer 2 key: identity by *content* -> catches the same role posted
        on a second board (different uid, same hash)."""
        basis = f"{normalize(self.company)}|{normalize(self.title)}|{self.region}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()
