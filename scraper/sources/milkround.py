"""Source: Milkround (Cloudflare-fronted HTML).

Milkround is a broad graduate board on the StepStone platform. It sits behind
Cloudflare, so I fetch it with the browser-fingerprint helper, and its results
are server-rendered: each job is an <article> whose heading links to the role's
own totaljobs.com page, with the employer, location and salary as ordered text
nodes underneath. Those totaljobs links are the specific role pages.

Milkround covers every sector, so I read its technology categories and keep only
genuine tech roles with the shared classifier.
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

BASE = "https://www.milkround.com"

# Milkround's technology categories. Both are broad, so the classifier still does
# the final tech filtering; the default type is graduate because that is what the
# board mostly carries.
LISTINGS = [
    "/jobs/graduate-technology",
    "/jobs/it-technology",
]

_JOB_RE = re.compile(r"(?:totaljobs\.com|milkround\.com)/job/")
# A digit is required before "k" so "£30k" reads as pay but "London, UK" does not.
_SALARY_RE = re.compile(r"[£$€]|competitive|per annum|per year|\d+k\b", re.I)
# Milkround aggregates totaljobs, which mixes in recruitment-agency reposts and
# unrelated sectors, so its reject list is the widest: the usual non-computing
# engineering plus recruitment, medical, teaching and the other noise totaljobs
# floods a technology search with.
_NON_COMPUTING_RE = re.compile(
    r"\b(civil|structural|mechanical|chemical|mining|geotechnical|marine|"
    r"aerospace|automotive|architectur|quantity survey|hvac|audit|accounts|"
    r"marketing|sales|nursing|teaching|care assistant|recruitment|recruiter|"
    r"nutrition|radiotherapy|radiograph|dental|veterinar|residential|"
    r"warehouse|driver|hospitality|retail assistant)\b",
    re.I,
)


def _card_of(anchor):
    """Climb to the <article> that wraps one Milkround result."""
    node = anchor
    for _ in range(6):
        if node is None:
            break
        if node.name == "article":
            return node
        node = node.parent
    return anchor.parent


def parse_listing(html: str, ctx) -> int:
    """Insert every tech role on one rendered Milkround category page."""
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        if not _JOB_RE.search(a["href"]):
            continue
        role = " ".join(a.get_text(" ", strip=True).split())
        href = a["href"].split("?")[0]
        if not role or href in seen:
            continue
        seen.add(href)

        if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
            continue
        if _NON_COMPUTING_RE.search(role):
            continue
        if not _has_tech_keyword(role.lower()):
            continue

        # Card text nodes: role, employer, location, salary. I take the employer
        # and location by order and skip the salary line if it lands in the
        # location slot.
        card = _card_of(a)
        nodes = [t for t in card.stripped_strings] if card else []
        company = ""
        location = ""
        salary = ""
        if role in nodes:
            rest = nodes[nodes.index(role) + 1:]
            if rest:
                company = rest[0]
            for node in rest[1:]:
                if _SALARY_RE.search(node) and not salary:
                    salary = node
                elif not location and not _SALARY_RE.search(node):
                    location = node
        if not company:
            continue

        if insert_job(ctx, {
            "company":      company,
            "role":         role,
            "type":         infer_type(role, default="Graduate"),
            "url":          urljoin(BASE, href),
            "location":     normalize_location(location),
            "salary_range": salary,
            "source":       "Milkround",
        }):
            count += 1
    return count


def scrape_milkround(ctx) -> int:
    """Page through each Milkround technology category until a page adds nothing."""
    print("\nScraping Milkround...")
    total = 0
    for path in LISTINGS:
        count = 0
        for page in range(1, 16):
            html = browser_get(f"{BASE}{path}", params={"page": page})
            if not html:
                break
            added = parse_listing(html, ctx)
            count += added
            if added == 0:
                break
        if count:
            print(f"  {path.rsplit('/', 1)[-1]}: {count} new")
        total += count
    print(f"  Milkround total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- Milkround ---")
    try:
        n = scrape_milkround(ctx)
        record_stat(ctx, "Milkround", n)
        return n
    except Exception as e:
        print(f"  Error Milkround: {e}")
        record_stat(ctx, "Milkround", 0, str(e))
        return 0
