"""Source: Prospects (rendered results).

Prospects is the UK graduate careers service's job board. It challenges every
client - even a real browser fingerprint gets the Cloudflare interstitial - so
the results page always goes through the Scrapling Camoufox render. The
rendered cards are labelled: the anchor is the role and its own posting page,
then "Employer name", "Location" and "Salary" each precede their value, so the
parse reads label-value pairs instead of guessing at text order.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http_browser import browser_render
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.prospects.ac.uk"

# One render per search. The graduate-jobs results carry placements and
# internships too (typed from their titles); a work-experience-results route
# does not exist, it 404s.
SEARCHES = ["software engineering", "computer science"]

_JOB_RE = re.compile(
    r"/(?:graduate-jobs/[a-z0-9-]+|employer-profiles/[a-z0-9-]+/jobs/[a-z0-9-]+)-\d{5,}"
)

_LABELS = {"Employer name": "company", "Location": "location", "Salary": "salary"}


def parse_cards(page_html: str) -> list[dict]:
    """Return the {role, company, location, salary, url} of every rendered card."""
    soup = BeautifulSoup(page_html, "html.parser")
    cards = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if not _JOB_RE.search(href) or href in seen:
            continue
        role = " ".join(a.get_text(" ", strip=True).split())
        if not role:
            continue
        seen.add(href)
        # Climb to the wrapper that carries the labelled fields.
        card = a
        for _ in range(8):
            if card.parent is None:
                break
            card = card.parent
            if any(lbl in card.get_text() for lbl in _LABELS):
                break
        fields = {"company": "", "location": "", "salary": ""}
        nodes = list(card.stripped_strings)
        for i, node in enumerate(nodes[:-1]):
            key = _LABELS.get(node)
            if key and not fields[key]:
                fields[key] = nodes[i + 1]
        cards.append({
            "role": role,
            "url":  urljoin(BASE, href),
            **fields,
        })
    return cards


def scrape_prospects(ctx) -> int:
    """Render each search's results and keep the student tech roles."""
    print("\nScraping Prospects...")
    total = 0
    for term in SEARCHES:
        page_html = browser_render(
            f"{BASE}/graduate-jobs-results",
            params={"search": term, "size": 20},
            wait_selector='a[href*="-2"]',
        )
        if not page_html:
            continue
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
                "type":         infer_type(role, default="Graduate"),
                "url":          card["url"],
                "location":     normalize_location(card["location"]),
                "salary_range": card["salary"],
                "source":       "Prospects",
            }):
                total += 1
    print(f"  Prospects total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- Prospects ---")
    try:
        n = scrape_prospects(ctx)
        record_stat(ctx, "Prospects", n)
        return n
    except Exception as e:
        print(f"  Error Prospects: {e}")
        record_stat(ctx, "Prospects", 0, str(e))
        return 0
