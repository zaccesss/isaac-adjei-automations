"""The ordered source registry: every scraper in its long-standing execution order.

Each entry is (name, mode, gated, run). mode selects which SCRAPER_MODE job the
source belongs to. gated marks the sources the old main() wrapped in an over-budget
check; the browser pair and the first four API families manage the budget
internally, so they stay ungated to keep the behaviour identical.
"""
from . import (
    adzuna,
    amazon,
    apple,
    arbeitnow,
    ashby,
    company_sites,
    greenhouse,
    jobicy,
    jooble,
    lever,
    microsoft,
    reed,
    remotive,
    smartrecruiters,
    trackr,
    workday,
)

SOURCES = [
    ("The Trackr", "browser", False, trackr.run),
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
