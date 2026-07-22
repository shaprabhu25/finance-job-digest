# Data layer — design of record

The foundation the whole scraper stands on. Built and **proven first**, before any
fetchers. `python3 test_state.py` → 12/12 pass against the 5 acceptance criteria.

## Three stores

| # | Store | Backend | Who writes it |
|---|-------|---------|---------------|
| 1 | Company registry (input) | Google Sheet → published CSV | The friend (no code) |
| 2 | Seen/dedupe state | `state/seen.jsonl` in the repo | The Action, each run |
| 3 | Normalized `Job` | in-memory only | The code, each run |

## Store 1 — the sheet (`companies.sample.csv` is the template)
Columns: `company_name, ats_type, slug_or_url, active, tags, notes`
- `ats_type` ∈ greenhouse | lever | ashby | workday | smartrecruiters | workable | recruitee | scrape
- `active` = yes/no soft toggle (never delete rows)
- Read-only fetch via "Publish to web → CSV" → **no auth, no API keys ever**

### How the friend spots the ATS (5-line cheat-sheet)
Open a company's careers page, read the URL:
- `boards.greenhouse.io/COMPANY` → greenhouse, slug = COMPANY
- `jobs.lever.co/COMPANY` → lever, slug = COMPANY
- `jobs.ashbyhq.com/COMPANY` → ashby, slug = COMPANY
- `…myworkdayjobs.com/…` → workday, paste the full URL
- none of the above → scrape, paste the full careers URL

## Store 2 — the two dedupe keys (the core)
- `job_uid = "{source}:{native_id}"` — Layer 1. Perfect same-source dedupe.
  Scraped pages (no id) fall back to `sha1(apply_url)`.
- `content_hash = sha1(company | title | region)` — Layer 2. Catches the same
  role reposted on another board. `region` ∈ {india, remote_ww, other};
  Bengaluru and remote-India both map to `india` so board-phrasing differences
  don't leak duplicates.

Decision rule per job: seen uid → skip · else seen hash → skip (cross-board) ·
else **new** → send.

Lifecycle: prune records whose `last_seen` > 60 days old. A live job is re-seen
every run so it never prunes while open (→ never resent); once it's gone 60 days
it's forgotten (→ a genuine re-opening is caught).

## The one trade-off, stated on purpose
`content_hash` uses company+title+region. Benefit: cross-board reposts collapse
to one card. Cost: if a company has **two genuinely different reqs with the same
title in the same region** (e.g. two "Manager, Audit" at Deloitte India), they
collapse into one card. For a senior applicant this is acceptable — he applies to
the company for that title once and sees all reqs on their board. Loosen later by
adding the native id back into the hash if we ever want every req shown.

## Swap-ability
Pipeline only ever calls `load_state / partition / commit / prune / save_state`.
Moving to Supabase/Sheets later = reimplement `load_state`/`save_state` only.
Nothing else changes.
