"""Accept/reject rules. Three gates, all must pass: role, level, location.

Tuned to the brief:
  roles  = FP&A/corporate finance + accounting/audit + fintech finance ops
  level  = senior (6+ yrs) -> keep manager/lead/controller/director; drop juniors
  place  = Bangalore OR remote (India / worldwide / unspecified); drop foreign
"""
from __future__ import annotations

import re

from models import Job

# --- role gate --------------------------------------------------------------
_INCLUDE = (
    "finance", "financial", "fp&a", "fpna", "financial planning", "controller",
    "controllership", "treasury", "accounting", "accountant", "accounts",
    "audit", "auditor", "assurance", "taxation", "tax ", "compliance",
    "revenue operations", "revenue ops", "finance operations", "finance ops",
    "business finance", "finance business partner", "financial analyst",
    "corporate finance", "cost accounting", "financial reporting",
)
# Kills false positives that contain a finance word but aren't finance roles.
_EXCLUDE = (
    "sales", "account executive", "account manager", "account director",
    "financial advisor", "financial adviser", "wealth manager", "relationship manager",
    "marketing", "engineer", "developer", "designer", "recruiter", "customer",
    "sdr", "bdr", "growth", "software", "data scientist", "product manager",
)

# --- level gate (senior: drop clearly-junior) -------------------------------
# Word-boundary matched: "intern" must NOT fire on "International", "graduate"
# must NOT fire on "undergraduate-adjacent" text, etc.
_JUNIOR_RE = re.compile(
    r"\b(intern|internship|trainee|graduate|apprentice|fresher|entry[ -]?level|junior|campus)\b",
    re.I,
)


def role_ok(title: str) -> bool:
    t = (title or "").lower()
    if any(x in t for x in _EXCLUDE):
        return False
    return any(x in t for x in _INCLUDE)


# Target experience band. Roles that STATE a required minimum outside this are
# dropped; roles that don't state one are kept (most posts omit it). Small margin
# around the 5-10 ask: 4 catches "4+ yrs" he over-qualifies for, 11 catches
# "10+ yrs" phrasings; 3-and-under and 12+ are dropped as off-target.
YOE_MIN_OK = 4
YOE_MAX_OK = 11


def level_ok(title: str, yoe_min) -> bool:
    if _JUNIOR_RE.search(title or ""):
        return False
    if yoe_min is None:                    # unstated -> keep (honest; most posts)
        return True
    return YOE_MIN_OK <= yoe_min <= YOE_MAX_OK


_ACCEPT_BUCKETS = {"bengaluru", "remote_india", "remote_ww", "remote_unspecified"}


def location_ok(job: Job) -> bool:
    return job.location_bucket in _ACCEPT_BUCKETS


def passes(job: Job) -> bool:
    return role_ok(job.title) and level_ok(job.title, job.yoe_min) and location_ok(job)
