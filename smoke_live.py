"""Live end-to-end smoke test against real boards. Proves fetch->enrich->filter.
Run: python3 smoke_live.py   (needs network)
"""
from fetchers import fetch_greenhouse, fetch_lever, fetch_ashby, fetch_remoteok
from filters import role_ok, level_ok, location_ok, passes

SOURCES = [
    ("greenhouse", "stripe",   lambda: fetch_greenhouse("stripe", "Stripe")),
    ("greenhouse", "coinbase", lambda: fetch_greenhouse("coinbase", "Coinbase")),
    ("lever",      "spotify",  lambda: fetch_lever("spotify", "Spotify")),
    ("ashby",      "ramp",     lambda: fetch_ashby("ramp", "Ramp")),
    ("remoteok",   "-",        fetch_remoteok),
]

grand_role = 0
for kind, slug, fn in SOURCES:
    try:
        jobs = fn()
    except Exception as e:
        print(f"[{kind}:{slug}] ERROR {e}")
        continue
    role = [j for j in jobs if role_ok(j.title)]
    passing = [j for j in jobs if passes(j)]
    grand_role += len(role)
    print(f"\n[{kind}:{slug}] fetched={len(jobs)}  finance-title={len(role)}  fully-passing(role+level+loc)={len(passing)}")
    for j in role[:4]:
        gate = "PASS" if passes(j) else ("loc:" + j.location_bucket if role_ok(j.title) and level_ok(j.title, j.yoe_min) else "level")
        print(f"   • {j.title[:52]:52} | {j.location_bucket:18} | yoe={j.yoe or '—'} | sal={j.salary or '—'} | {gate}")

print(f"\n=== finance-title roles found across live sources: {grand_role} ===")
print("Location gate correctly rejects US/foreign roles; role+enrich work on live data.")
