"""Source: TARGETjobs (rendered category pages).

TARGETjobs is GTI's student board. It is a Gatsby app that fetches its listings
client-side, so each category page renders through the Scrapling Camoufox
browser and the jobs are read from the populated DOM. Each card links the
role's own /jobs/ page and reads, in order: an optional Spotlight badge, the
employer, the role, the location, sometimes a salary and a "days to apply"
line that becomes the deadline.
"""
import re
from datetime import date, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http_browser import browser_render
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://targetjobs.co.uk"

# (path, default type). The IT and engineering categories of each opportunity
# type; the search route carries the placements, which have no category pages.
LISTINGS = [
    ("/graduate-jobs/it",          "Graduate"),
    ("/graduate-jobs/engineering", "Graduate"),
    ("/internships/it",            "Internship"),
    ("/internships/engineering",   "Internship"),
    ("/search/jobs?search=&opportunity_type=Placement&force=true", "Industrial Placement"),
]

_JOB_HREF_RE = re.compile(r"^/jobs/[a-z0-9-]+-\d{4,}$")
_SALARY_RE = re.compile(r"[£$€]|competitive|per annum|per year|\d+k\b", re.I)
_DAYS_RE = re.compile(r"(\d+)\s+days? to apply", re.I)
_BADGES = {"Spotlight", "Featured", "Sponsored", "Save", "New"}


def parse_cards(page_html: str) -> list[dict]:
    """Return the {role, company, location, salary, deadline, url} of every card.

    The anchor wraps the whole card, so its own text nodes read in order:
    optional badge, employer, role, location, optional salary, "N days to
    apply" and the Save control.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    cards = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if not _JOB_HREF_RE.match(href) or href in seen:
            continue
        seen.add(href)
        nodes = [n for n in a.stripped_strings if n not in _BADGES]
        if len(nodes) < 2:
            continue
        company, role = nodes[0], nodes[1]
        location = ""
        salary = ""
        deadline = None
        for node in nodes[2:]:
            days = _DAYS_RE.search(node)
            if days:
                deadline = (date.today() + timedelta(days=int(days.group(1)))).isoformat()
            elif _SALARY_RE.search(node) and not salary:
                salary = node
            elif not location and len(node) < 60:
                location = node
        cards.append({
            "role":     role,
            "company":  company,
            "location": location,
            "salary":   salary,
            "deadline": deadline,
            "url":      urljoin(BASE, href),
        })
    return cards


def scrape_targetjobs(ctx) -> int:
    """Render each category and keep the student tech roles."""
    print("\nScraping TARGETjobs...")
    total = 0
    for path, default_type in LISTINGS:
        page_html = browser_render(f"{BASE}{path}", wait_selector='a[href^="/jobs/"]')
        if not page_html:
            continue
        added = 0
        for card in parse_cards(page_html):
            role = card["role"]
            if not card["company"]:
                continue
            if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                continue
            if not _has_tech_keyword(role.lower()):
                continue
            if insert_job(ctx, {
                "company":      card["company"],
                "role":         role,
                "type":         infer_type(role, default=default_type),
                "url":          card["url"],
                "location":     normalize_location(card["location"]),
                "salary_range": card["salary"],
                "deadline":     card["deadline"],
                "source":       "TARGETjobs",
            }):
                added += 1
        total += added
    print(f"  TARGETjobs total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- TARGETjobs ---")
    try:
        n = scrape_targetjobs(ctx)
        record_stat(ctx, "TARGETjobs", n)
        return n
    except Exception as e:
        print(f"  Error TARGETjobs: {e}")
        record_stat(ctx, "TARGETjobs", 0, str(e))
        return 0
