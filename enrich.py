"""Best-effort extraction of years-of-experience and salary from free text.

Rule that matters: when we can't find it cleanly, return None -> the card shows
"not specified". We NEVER guess. A wrong "3 yrs" is worse than "not specified".
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# "5+ years", "3-5 years", "3 to 5 yrs", "minimum 4 years", "at least 6 years exp"
_YOE_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\+?\s*(?:years|yrs|yr)\b", re.I)
_YOE_PLUS = re.compile(r"(\d{1,2})\s*\+\s*(?:years|yrs|yr)\b", re.I)
_YOE_MIN = re.compile(r"(?:minimum|min\.?|at least|over)\s*(?:of\s*)?(\d{1,2})\s*(?:years|yrs|yr)\b", re.I)
_YOE_PLAIN = re.compile(r"\b(\d{1,2})\s*(?:years|yrs|yr)\b(?:\s*(?:of)?\s*(?:experience|exp))", re.I)


def extract_yoe(text: str) -> Tuple[Optional[str], Optional[int]]:
    """Return (display, min_years). min_years drives the level filter."""
    t = text or ""
    m = _YOE_RANGE.search(t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (f"{lo}–{hi} yrs", lo)
    m = _YOE_PLUS.search(t)
    if m:
        n = int(m.group(1))
        return (f"{n}+ yrs", n)
    m = _YOE_MIN.search(t)
    if m:
        n = int(m.group(1))
        return (f"{n}+ yrs", n)
    m = _YOE_PLAIN.search(t)
    if m:
        n = int(m.group(1))
        return (f"{n} yrs", n)
    return (None, None)


# ₹20-30 LPA · 20 LPA · Rs. 15,00,000 · $120k-160k · INR 25 lakh
_SAL_LPA = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:-|to|–)?\s*(\d{1,3}(?:[.,]\d{1,2})?)?\s*(?:lpa|lakhs?\s*(?:per\s*annum|p\.?a\.?)?)", re.I)
_SAL_USD = re.compile(r"\$\s?(\d{2,3})\s?k\s*(?:-|to|–)?\s*\$?\s?(\d{2,3})?\s?k?", re.I)
_SAL_INR = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]{5,})", re.I)


def extract_salary(text: str, structured: Optional[str] = None) -> Optional[str]:
    """structured = a salary string a source already gave us (Ashby/RemoteOK)."""
    if structured:
        return structured
    t = text or ""
    m = _SAL_LPA.search(t)
    if m:
        lo, hi = m.group(1), m.group(2)
        return f"₹{lo}–{hi} LPA" if hi else f"₹{lo} LPA"
    m = _SAL_USD.search(t)
    if m:
        lo, hi = m.group(1), m.group(2)
        return f"${lo}k–${hi}k" if hi else f"${lo}k"
    m = _SAL_INR.search(t)
    if m:
        return f"₹{m.group(1)}"
    return None
