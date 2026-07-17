"""The ordered source registry: every scraper in its long-standing execution order.

Each entry is (name, mode, gated, run). mode selects which SCRAPER_MODE job the
source belongs to. gated marks the sources the old main() wrapped in an over-budget
check; The Trackr, the company-sites browser source and the first four API families
manage the budget internally, so they stay ungated to keep the behaviour identical.

The Trackr now runs in the fast "api" job: it reads the api.the-trackr.com
programmes JSON directly, so it no longer needs the Playwright install the browser
job carries for the company-sites source.
"""
from . import (
    adzuna,
    amazon,
    apple,
    arbeitnow,
    ashby,
    brightnetwork,
    company_sites,
    gradcracker,
    greenhouse,
    jobicy,
    jooble,
    lever,
    microsoft,
    milkround,
    ratemyplacement,
    reed,
    remotive,
    smartrecruiters,
    trackr,
    workday,
)

SOURCES = [
    ("The Trackr", "api", False, trackr.run),
    ("RateMyPlacement", "api", True, ratemyplacement.run),
    ("Gradcracker", "api", True, gradcracker.run),
    ("Bright Network", "api", True, brightnetwork.run),
    ("Milkround", "api", True, milkround.run),
    ("Company career sites", "browser", False, company_sites.run),
    ("Greenhouse", "api", False, greenhouse.run),
    ("Lever", "api", False, lever.run),
    ("Ashby", "api", False, ashby.run),
    ("SmartRecruiters", "api", False, smartrecruiters.run),
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
