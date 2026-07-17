"""Source: StudentJob UK (server-rendered HTML).

StudentJob renders its vacancy search as plain HTML: each result is a card
wrapped in its own /vacancies/{id}-{slug} anchor, with the role as the first
text line, the employer as the logo's title attribute and the location under
a location icon. The board is mostly part-time and gig work, so the tech
keyword filter and the widest reject list do the real work; what survives is
the occasional genuine internship or placement the bigger boards missed.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http_browser import browser_get
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.studentjob.co.uk"

SEARCHES = ["software", "engineering", "data"]

_JOB_HREF_RE = re.compile(r"/vacancies/\d+-")
_SALARY_RE = re.compile(r"[£$€]|per hour|per week|per month|per annum|\d+k\b", re.I)
# Survey, gig and non-tech noise this board is full of.
_NON_COMPUTING_RE = re.compile(
    r"\b(your own opinion|survey|paid test|game tester|mystery shop|tutor|"
    r"delivery|driver|warehouse|barista|waiter|bartend|retail|nanny|babysit|"
    r"care assistant|sales|promoter|charity|fundrais)\b",
    re.I,
)


def parse_cards(page_html: str) -> list[dict]:
    """Return the {role, company, location, salary, url} of every job card."""
    soup = BeautifulSoup(page_html, "html.parser")
    cards = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=_JOB_HREF_RE):
        href = a["href"].split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        nodes = list(a.stripped_strings)
        if not nodes:
            continue
        role = nodes[0]
        logo = a.find(attrs={"title": True})
        company = (logo.get("title") or "").strip() if logo else ""
        location = ""
        salary = ""
        for node in nodes[1:]:
            if _SALARY_RE.search(node):
                salary = salary or node
            elif not location and len(node) < 60:
                location = node
        cards.append({
            "role":     role,
            "company":  company,
            "location": location,
            "salary":   salary,
            "url":      urljoin(BASE, href),
        })
    return cards


def scrape_studentjob(ctx) -> int:
    """Run each keyword search and keep the genuine student tech roles."""
    print("\nScraping StudentJob...")
    total = 0
    for term in SEARCHES:
        page_html = browser_get(
            f"{BASE}/vacancies", params={"search[keywords]": term}
        )
        if not page_html:
            continue
        for card in parse_cards(page_html):
            role = card["role"]
            if not card["company"]:
                continue
            if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                continue
            if _NON_COMPUTING_RE.search(role):
                continue
            if not _has_tech_keyword(role.lower()):
                continue
            if insert_job(ctx, {
                "company":      card["company"],
                "role":         role,
                "type":         infer_type(role, default="Internship"),
                "url":          card["url"],
                "location":     normalize_location(card["location"]),
                "salary_range": card["salary"],
                "source":       "StudentJob",
            }):
                total += 1
    print(f"  StudentJob total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- StudentJob ---")
    try:
        n = scrape_studentjob(ctx)
        record_stat(ctx, "StudentJob", n)
        return n
    except Exception as e:
        print(f"  Error StudentJob: {e}")
        record_stat(ctx, "StudentJob", 0, str(e))
        return 0
