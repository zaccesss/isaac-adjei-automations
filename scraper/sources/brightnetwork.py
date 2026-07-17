"""Source: Bright Network (Cloudflare-fronted HTML).

Bright Network sits behind Cloudflare like Gradcracker, so I fetch it with the
browser-fingerprint helper, but its result cards are server-rendered HTML. Each
card is a `search-result-card` div linking to the role's own
/graduate-jobs/{employer}/{slug} page, with the employer, location and deadline
as ordered text nodes. Those links are the specific role pages.

The board mixes every discipline, so I read the internships and the graduate
listings and keep only genuine tech roles with the shared classifier.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import (
    _NON_TECH_ROLE_RE,
    _SENIOR_ROLE_RE,
    _has_tech_keyword,
    infer_type,
)
from ..http_browser import browser_get
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.brightnetwork.co.uk"

# (listing path, default type). The path is Bright Network's routing, not a
# reliable type - its internships route links to /graduate-jobs/ URLs too - so I
# take the type from the listing I am reading and let the title refine it.
LISTINGS = [
    ("/internships/", "Internship"),
    ("/graduate-jobs/", "Graduate"),
]

_JOB_RE = re.compile(r"^/(?:graduate-jobs|internships|work-experience)/[^/]+/[^/?]+")
_ORDINAL_RE = re.compile(r"(\d+)(?:st|nd|rd|th)", re.I)
# The non-computing engineering and commercial leakage the tech feed still shows.
_NON_COMPUTING_RE = re.compile(
    r"\b(civil|structural|mechanical|chemical|mining|geotechnical|marine|"
    r"aerospace|automotive|architectur|quantity survey|hvac|audit|accounts|"
    r"production assistant|marketing|human factors)\b",
    re.I,
)


def _parse_deadline(text: str) -> "str | None":
    """Parse "30th Sep 2026" to an ISO date; rolling deadlines return None."""
    if not text:
        return None
    cleaned = _ORDINAL_RE.sub(r"\1", text).strip()
    from datetime import datetime
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _card_of(anchor):
    """Climb to the search-result-card wrapper for one role."""
    node = anchor
    for _ in range(8):
        if node is None:
            break
        classes = node.get("class") or []
        if any("search-result-card" in c for c in classes):
            return node
        node = node.parent
    return anchor.parent


def parse_listing(html: str, default_type: str, ctx) -> int:
    """Insert every tech role on one rendered Bright Network listing page."""
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        if not _JOB_RE.match(a["href"]):
            continue
        href = urljoin(BASE, a["href"].split("?")[0])
        role = " ".join(a.get_text(" ", strip=True).split())
        if not role or href in seen:
            continue
        seen.add(href)

        if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
            continue
        if _NON_COMPUTING_RE.search(role):
            continue
        if not _has_tech_keyword(role.lower()):
            continue

        # The card text nodes come in the order role, employer, location,
        # "Deadline:", date. I read the employer and location off that order and
        # find the date after the Deadline label.
        card = _card_of(a)
        nodes = [t for t in card.stripped_strings] if card else []
        company = ""
        location = ""
        deadline = None
        if role in nodes:
            i = nodes.index(role)
            rest = nodes[i + 1:]
            if rest:
                company = rest[0]
            if len(rest) > 1 and not rest[1].lower().startswith("deadline"):
                location = rest[1]
            for j, node in enumerate(rest):
                if node.lower().startswith("deadline") and j + 1 < len(rest):
                    deadline = _parse_deadline(rest[j + 1])
                    break
        if not company:
            continue

        if insert_job(ctx, {
            "company":  company,
            "role":     role,
            "type":     infer_type(role, default=default_type),
            "url":      href,
            "location": normalize_location(location),
            "deadline": deadline,
            "source":   "Bright Network",
        }):
            count += 1
    return count


def scrape_brightnetwork(ctx) -> int:
    """Page through each Bright Network listing until a page adds nothing."""
    print("\nScraping Bright Network...")
    total = 0
    for path, default_type in LISTINGS:
        count = 0
        for page in range(1, 21):
            html = browser_get(f"{BASE}{path}", params={"page": page})
            if not html:
                break
            added = parse_listing(html, default_type, ctx)
            count += added
            if added == 0:
                break
        if count:
            print(f"  {path.strip('/')}: {count} new")
        total += count
    print(f"  Bright Network total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- Bright Network ---")
    try:
        n = scrape_brightnetwork(ctx)
        record_stat(ctx, "Bright Network", n)
        return n
    except Exception as e:
        print(f"  Error Bright Network: {e}")
        record_stat(ctx, "Bright Network", 0, str(e))
        return 0
