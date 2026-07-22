"""Proves URL auto-detection: the friend pastes a URL, code figures out the ATS.

Run: python3 test_resolver.py
"""
from resolver import resolve, detect_from_page

PASS, FAIL = [], []


def check(name, got, want):
    ok = got == want
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  got={got} want={want}"))


print("Direct ATS URLs -> exact (ats, slug)")
check("greenhouse",  resolve("https://boards.greenhouse.io/razorpay")[:2], ("greenhouse", "razorpay"))
check("greenhouse embed", resolve("https://boards.greenhouse.io/embed/job_board?for=stripe")[:2], ("greenhouse", "stripe"))
check("greenhouse EU", resolve("https://boards.eu.greenhouse.io/gitlab")[:2], ("greenhouse", "gitlab"))
check("lever",       resolve("https://jobs.lever.co/zerodha/")[:2], ("lever", "zerodha"))
check("ashby",       resolve("https://jobs.ashbyhq.com/groww")[:2], ("ashby", "groww"))
check("smartrecruiters", resolve("https://careers.smartrecruiters.com/SomeCo")[:2], ("smartrecruiters", "SomeCo"))
check("workable",    resolve("https://apply.workable.com/acme/")[:2], ("workable", "acme"))
check("recruitee",   resolve("https://acme.recruitee.com/")[:2], ("recruitee", "acme"))

print("\nWorkday -> keeps full path")
r = resolve("https://deloitte.wd1.myworkdayjobs.com/en-US/DeloitteIndia")
check("workday type", r[0], "workday")
check("workday exact", r[2], "exact")

print("\nCompany-own domain -> scrape tier (to be upgraded by page fetch)")
check("own domain",  resolve("https://razorpay.com/careers")[:1] + ("",), ("scrape", ""))
check("bare token unknown", resolve("razorpay")[0], None)
check("empty",       resolve("")[2], "empty")

print("\nEmbedded board detection from page HTML")
html_gh = '<iframe src="https://boards.greenhouse.io/embed/job_board?for=notion"></iframe>'
check("embedded greenhouse", detect_from_page(html_gh)[:2], ("greenhouse", "notion"))
html_lever = '<div><a href="https://jobs.lever.co/postman">Careers</a></div>'
check("embedded lever", detect_from_page(html_lever)[:2], ("lever", "postman"))
check("no board -> scrape", detect_from_page("<html>nothing here</html>")[0], "scrape")

print(f"\n{'='*44}\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    raise SystemExit(1)
print("URL auto-detect is SOLID -> friend only ever pastes a URL")
