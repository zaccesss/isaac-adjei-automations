"""Source: LinkedIn guest job search.

LinkedIn serves logged-out visitors a keyless guest endpoint that returns the
same result cards its public job search shows: title, company, location and the
posting's own /jobs/view/ page. No account and no cookie is involved, so there
is nothing to ban; the risk is only rate limiting, which is why this source
stays small - a handful of tight student-role queries scoped to the last week,
one page each - and fails soft to zero rows on any non-200.

Most of these roles are cross-posts of ATS listings other sources already
carry; the company+role dedupe collapses those onto the existing row and the
direct ATS link wins, so LinkedIn only ever fills genuine gaps.
"""
import html as _html
import re
import time

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http_browser import _curl_cffi_get
from ..locations import normalize_location
from ..stats import record_stat

_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# One page of each: every discipline the tracker covers, phrased the way UK
# student postings title themselves. f_TPR=r604800 keeps it to the last week,
# so the volume stays a trickle of genuinely new postings.
QUERIES = [
    "software industrial placement",
    "software engineer intern",
    "graduate software engineer",
    "hardware engineer intern",
    "machine learning intern",
    "data analyst placement",
]

_LINK_RE = re.compile(r'base-card__full-link[^>]*href="([^"]+)"')
_TITLE_RE = re.compile(r'base-search-card__title[^>]*>\s*([^<]+?)\s*<')
_COMPANY_RE = re.compile(r'hidden-nested-link[^>]*>\s*([^<]+?)\s*<')
_LOCATION_RE = re.compile(r'job-search-card__location[^>]*>\s*([^<]+?)\s*<')


def parse_cards(page_html: str) -> list[dict]:
    """Return the {role, company, location, url} of every card in a guest result page."""
    cards = []
    # Each result is one <li>; splitting keeps every regex scoped to its own
    # card so a missing field never shifts the remaining cards out of line.
    for chunk in page_html.split("<li")[1:]:
        link = _LINK_RE.search(chunk)
        title = _TITLE_RE.search(chunk)
        if not link or not title:
            continue
        company = _COMPANY_RE.search(chunk)
        location = _LOCATION_RE.search(chunk)
        cards.append({
            "role":     _html.unescape(title.group(1)).strip(),
            "company":  _html.unescape(company.group(1)).strip() if company else "",
            "location": _html.unescape(location.group(1)).strip() if location else "",
            "url":      _html.unescape(link.group(1)).split("?")[0],
        })
    return cards


def scrape_linkedin(ctx) -> int:
    """Run each guest query once and keep the UK student tech roles."""
    print("\nScraping LinkedIn guest search...")
    total = 0
    seen: set[str] = set()
    for query in QUERIES:
        page_html, status = _curl_cffi_get(
            _ENDPOINT,
            params={
                "keywords": query,
                "location": "United Kingdom",
                "f_TPR": "r604800",
                "start": 0,
            },
            timeout=20,
        )
        if not page_html:
            # 429 means the runner's IP is being limited; every query after it
            # would meet the same wall, so stop quietly rather than hammer on.
            print(f"  LinkedIn: HTTP {status} on '{query}'"
                  + (" - stopping" if status == 429 else ""))
            if status == 429:
                break
            continue
        for card in parse_cards(page_html):
            role = card["role"]
            if not card["company"] or card["url"] in seen:
                continue
            seen.add(card["url"])
            if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                continue
            if not _has_tech_keyword(role.lower()):
                continue
            if insert_job(ctx, {
                "company":  card["company"],
                "role":     role,
                "type":     infer_type(role, default="Internship"),
                "url":      card["url"],
                "location": normalize_location(card["location"]),
                "source":   "LinkedIn",
            }):
                total += 1
        time.sleep(1.5)
    print(f"  LinkedIn total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- LinkedIn guest search ---")
    try:
        n = scrape_linkedin(ctx)
        record_stat(ctx, "LinkedIn", n)
        return n
    except Exception as e:
        print(f"  Error LinkedIn: {e}")
        record_stat(ctx, "LinkedIn", 0, str(e))
        return 0
