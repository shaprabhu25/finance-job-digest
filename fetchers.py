"""Source fetchers. Each returns a list of normalized `Job` objects.

Built against the LIVE response shapes verified on 2026-07-22:
  greenhouse  boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
  lever       api.lever.co/v0/postings/{slug}?mode=json
  ashby       api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
  remoteok    remoteok.com/api   (User-Agent required)

stdlib only (urllib) so the GitHub Action needs no pip install.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from typing import List, Optional
from urllib.parse import urlparse

from models import Job
from enrich import extract_yoe, extract_salary

_UA = "Mozilla/5.0 (compatible; job-digest/1.0)"
_TAGS = re.compile(r"<[^>]+>")


def _get_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _post_json(url: str, body: dict, timeout: int = 20):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": _UA, "Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _plain(text: str) -> str:
    return html.unescape(_TAGS.sub(" ", text or "")).strip()


def _enrich(job: Job, structured_salary: Optional[str] = None) -> Job:
    disp, mn = extract_yoe(job.description)
    job.yoe, job.yoe_min = disp, mn
    job.salary = extract_salary(job.description, structured_salary)
    return job


# --- ATS fetchers -----------------------------------------------------------
def fetch_greenhouse(slug: str, company: str = "") -> List[Job]:
    d = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    out = []
    for j in d.get("jobs", []):
        out.append(_enrich(Job(
            source="greenhouse", source_job_id=str(j["id"]),
            company=company or j.get("company_name") or slug,
            title=(j.get("title") or "").strip(),
            location_raw=(j.get("location") or {}).get("name", ""),
            apply_url=j.get("absolute_url", ""),
            posted_at=(j.get("first_published") or j.get("updated_at") or "")[:10] or None,
            description=_plain(j.get("content", "")),
        )))
    return out


def fetch_lever(slug: str, company: str = "") -> List[Job]:
    d = _get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in d if isinstance(d, list) else []:
        cats = j.get("categories") or {}
        loc = cats.get("location") or (cats.get("allLocations") or [""])[0]
        wt = j.get("workplaceType") or ""
        out.append(_enrich(Job(
            source="lever", source_job_id=str(j["id"]),
            company=company or slug,
            title=(j.get("text") or "").strip(),
            location_raw=f"{loc} {wt}".strip(),
            apply_url=j.get("hostedUrl") or j.get("applyUrl", ""),
            description=j.get("descriptionPlain") or _plain(j.get("description", "")),
        )))
    return out


def fetch_ashby(slug: str, company: str = "") -> List[Job]:
    d = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        if j.get("isRemote") and "remote" not in loc.lower():
            loc = f"{loc} Remote".strip()
        comp = j.get("compensation")
        sal = None
        if isinstance(comp, dict):
            summ = comp.get("compensationTierSummary") or comp.get("summary")
            sal = summ if isinstance(summ, str) else None
        out.append(_enrich(Job(
            source="ashby", source_job_id=str(j["id"]),
            company=company or slug,
            title=(j.get("title") or "").strip(),
            location_raw=loc,
            apply_url=j.get("jobUrl") or j.get("applyUrl", ""),
            posted_at=(j.get("publishedAt") or "")[:10] or None,
            description=j.get("descriptionPlain") or _plain(j.get("descriptionHtml", "")),
        ), structured_salary=sal))
    return out


_WD_URL = re.compile(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:([a-z]{2}-[A-Z]{2})/)?([^/?#]+)", re.I)
_WD_TERMS = ("finance", "accounting", "audit")   # narrow big tenants server-side


def fetch_workday(url: str, company: str = "") -> List[Job]:
    m = _WD_URL.search(url or "")
    if not m:
        return []
    tenant, wd, lang, site = m.group(1), m.group(2), m.group(3) or "en-US", m.group(4)
    host = f"{tenant}.{wd}.myworkdayjobs.com"
    cxs = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    seen, out = set(), []
    for term in _WD_TERMS:
        try:
            d = _post_json(cxs, {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term})
        except Exception as e:
            print(f"  ! workday {tenant}/{site} '{term}' -> {e}")
            continue
        for j in d.get("jobPostings", []):
            path = j.get("externalPath") or ""
            if path in seen:
                continue
            seen.add(path)
            out.append(_enrich(Job(
                source="workday", source_job_id=path.rsplit("_", 1)[-1] or path,
                company=company or tenant,
                title=(j.get("title") or "").strip(),
                location_raw=j.get("locationsText", ""),
                apply_url=f"https://{host}/{lang}/{site}{path}",
                description="",   # Workday list view has no description; yoe/salary -> not specified
            )))
    return out


# --- aggregator fetchers ----------------------------------------------------
def fetch_remoteok() -> List[Job]:
    d = _get_json("https://remoteok.com/api")
    out = []
    for j in d:
        if not isinstance(j, dict) or "position" not in j:
            continue
        smin, smax = j.get("salary_min") or 0, j.get("salary_max") or 0
        sal = f"${smin//1000}k–${smax//1000}k" if smin and smax else None
        out.append(_enrich(Job(
            source="remoteok", source_job_id=str(j.get("id")),
            company=html.unescape(j.get("company") or ""),
            title=html.unescape(j.get("position") or "").strip(),
            location_raw=(j.get("location") or "Remote"),
            apply_url=j.get("url") or j.get("apply_url", ""),
            posted_at=(j.get("date") or "")[:10] or None,
            description=_plain(j.get("description", "")),
        ), structured_salary=sal))
    return out


# --- dispatch ---------------------------------------------------------------
_ATS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


def fetch_company(ats_type: str, slug_or_url: str, company: str = "") -> List[Job]:
    try:
        if ats_type == "workday":
            return fetch_workday(slug_or_url, company)
        fn = _ATS.get(ats_type)
        if not fn:
            return []          # scrape tier handled elsewhere
        return fn(slug_or_url, company)
    except Exception as e:
        print(f"  ! fetch failed {ats_type}:{slug_or_url} -> {e}")
        return []
