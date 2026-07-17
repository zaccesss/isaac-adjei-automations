"""The ordered source registry: every scraper in its long-standing execution order.

Each entry is (name, mode, gated, run). mode selects which SCRAPER_MODE job the
source belongs to. gated marks the sources the old main() wrapped in an over-budget
check; The Trackr, the company-sites browser source and the first four API families
manage the budget internally, so they stay ungated to keep the behaviour identical.

The Trackr and RateMyPlacement run in the fast "api" job: they read JSON directly
and need no browser, as do the ATS families (Workable, Recruitee, Personio, Jibe),
the LinkedIn guest search and the boards whose pages parse without a render
(StudentJob, E4S). Gradcracker, Bright Network and Milkround run in the "browser"
job because their Cloudflare fallback is a real Camoufox browser (via Scrapling)
that the job installs alongside Playwright; their fast path is still a browserless
curl_cffi fetch, so only the boards Cloudflare hard-challenges pay the browser cost.
Prospects and TARGETjobs always render there: Prospects challenges every client
and TARGETjobs only builds its listings client-side.
"""
from . import (
    adzuna,
    amazon,
    apple,
    arbeitnow,
    ashby,
    brightnetwork,
    company_sites,
    e4s,
    eightfold,
    faang,
    gradcracker,
    greenhouse,
    jibe,
    jobicy,
    jooble,
    lever,
    linkedin_guest,
    microsoft,
    milkround,
    oracle_ce,
    personio,
    prospects,
    ratemyplacement,
    recruitee,
    reed,
    remotive,
    smartrecruiters,
    studentjob,
    targetjobs,
    trackr,
    workable,
    workday,
)

SOURCES = [
    ("The Trackr", "api", False, trackr.run),
    ("RateMyPlacement", "api", True, ratemyplacement.run),
    ("Gradcracker", "browser", True, gradcracker.run),
    ("Bright Network", "browser", True, brightnetwork.run),
    ("Milkround", "browser", True, milkround.run),
    ("Prospects", "browser", True, prospects.run),
    ("TARGETjobs", "browser", True, targetjobs.run),
    ("FAANG+ rendered", "browser", True, faang.run),
    ("Company career sites", "browser", False, company_sites.run),
    ("Greenhouse", "api", False, greenhouse.run),
    ("Lever", "api", False, lever.run),
    ("Ashby", "api", False, ashby.run),
    ("SmartRecruiters", "api", False, smartrecruiters.run),
    ("Eightfold", "api", True, eightfold.run),
    ("Oracle Recruiting Cloud", "api", True, oracle_ce.run),
    ("Workable", "api", True, workable.run),
    ("Recruitee", "api", True, recruitee.run),
    ("Personio", "api", True, personio.run),
    ("Jibe", "api", True, jibe.run),
    ("LinkedIn", "api", True, linkedin_guest.run),
    ("StudentJob", "api", True, studentjob.run),
    ("E4S", "api", True, e4s.run),
    ("Apple Careers", "api", True, apple.run),
    ("Microsoft Careers", "api", True, microsoft.run),
    ("Amazon Jobs", "api", True, amazon.run),
    ("Workday", "api", True, workday.run),
    ("Reed", "api", True, reed.run),
    ("Adzuna", "api", True, adzuna.run),
    ("Jooble", "api", True, jooble.run),
    ("Arbeitnow", "api", True, arbeitnow.run),
    ("Jobicy", "api", True, jobicy.run),
    ("Remotive", "api", True, remotive.run),
]
