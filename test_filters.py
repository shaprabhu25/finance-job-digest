"""Locks the filter gates, including the 'intern' vs 'International' bug.
Run: python3 test_filters.py
"""
from models import Job
from filters import role_ok, level_ok, location_ok, passes

P, F = [], []
def check(name, cond):
    (P if cond else F).append(name); print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


print("role gate")
check("FP&A included", role_ok("Manager, FP&A"))
check("accountant included", role_ok("Senior Accountant"))
check("audit included", role_ok("Internal Audit Lead"))
check("sales excluded", not role_ok("Sales Account Executive"))
check("financial advisor excluded", not role_ok("Financial Advisor"))
check("engineer excluded", not role_ok("Finance Data Engineer"))

print("\nlevel gate (senior)")
check("International NOT junior (the bug)", level_ok("Financial Partnerships Manager, International", 7))
check("intern IS junior", not level_ok("Finance Intern", None))
check("graduate IS junior", not level_ok("Graduate Finance Trainee", None))
check("<=2 yrs dropped", not level_ok("Finance Analyst", 2))
check("3 yrs (below band) dropped", not level_ok("Finance Analyst", 3))
check("5 yrs kept", level_ok("Finance Manager", 5))
check("6+ yrs kept", level_ok("Finance Manager", 6))
check("10 yrs kept", level_ok("Finance Director", 10))
check("12+ yrs (too senior) dropped", not level_ok("VP Finance", 12))
check("unknown yoe kept", level_ok("Financial Controller", None))

print("\nlocation gate")
def J(loc): return Job("x", "1", "C", "Finance Manager", loc)
check("Bengaluru accepted", location_ok(J("Bengaluru, India")))
check("remote India accepted", location_ok(J("Remote - India")))
check("remote worldwide accepted", location_ok(J("Remote (Worldwide)")))
check("bare remote accepted", location_ok(J("Remote")))
check("remote US rejected", not location_ok(J("Remote - United States")))
check("onsite NY rejected", not location_ok(J("New York, NY")))
check("onsite Mumbai rejected", not location_ok(J("Mumbai, India")))

print(f"\n{'='*40}\n{len(P)} passed, {len(F)} failed")
if F: raise SystemExit(1)
print("Filters SOLID ✓")
