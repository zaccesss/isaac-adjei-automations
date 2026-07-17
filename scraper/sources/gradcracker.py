"""Source: Gradcracker (Cloudflare-fronted HTML).

Gradcracker is the main UK STEM student board. It sits behind Cloudflare, so I
fetch it with the browser-fingerprint helper, but the listings themselves are
plain server-rendered HTML: each job is an anchor to its own
/hub/{id}/{employer}/{type}/{jobId}/{slug} page, with the employer in the logo
alt text and the deadline, salary and location labelled in the card.

I read the computing-technology discipline directly, so the feed is already tech
scoped, and I take both the placements/internships listing and the graduate-jobs
listing. Every link is the specific role page, which is exactly the direct apply
link the careers-page-only rows lack.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http_browser import browser_get
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.gradcracker.com"

# The two computing-technology listings. The type comes from each link's own URL
# segment, not the listing, because a page mixes its organic results with
# promoted roles of the other kind.
LISTINGS = [
    "/search/computing-technology/internships-work-placements",
    "/search/computing-technology/jobs",
]

_JOB_RE = re.compile(r"/hub/\d+/[^/]+/(work-placement-internship|graduate-job)/\d+/")
# The computing-technology feed still surfaces the odd promoted role from an
# adjacent engineering discipline (civil, mechanical, a mining webinar). None of
# these are software or hardware, so I drop a title that leads on one of them.
_NON_COMPUTING_RE = re.compile(
    r"\b(civil|structural|mechanical|chemical|mining|geotechnical|marine|"
    r"aerospace|automotive|architectur|quantity survey|hvac|building services|"
    r"m&e|human factors|webinar)\b",
    re.I,
)
_ORDINAL_RE = re.compile(r"(\d+)(?:st|nd|rd|th)", re.I)
_DEADLINE_RE = re.compile(r"Deadline:\s*(.+?)(?:\s+Salary|\s+Location|\s+Degree|\s+Starting|$)", re.I)
_LOCATION_RE = re.compile(r"Location\s+(.+?)(?:\s+Degree|\s+Starting|\s+Salary|$)", re.I)


def _parse_deadline(text: str) -> "str | None":
    """Best-effort parse of Gradcracker's "30th Sep 2026" into an ISO date.

    Ongoing and rolling deadlines have no date, so they return None and the row
    is stored without one rather than being dropped by the date cutoff.
    """
    if not text:
        return None
    cleaned = _ORDINAL_RE.sub(r"\1", text).strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y"):
        try:
            from datetime import datetime
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _card_of(anchor):
    """Climb to the smallest ancestor that carries the employer logo (its alt)."""
    node = anchor
    for _ in range(6):
        if node is None:
            break
        if node.find("img", alt=True):
            return node
        node = node.parent
    return anchor.parent


def parse_listing(html: str, ctx) -> int:
    """Insert every tech role on one rendered listing page."""
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = _JOB_RE.search(a["href"])
        if not m:
            continue
        href = urljoin(BASE, a["href"].split("?")[0])
        if href in seen:
            continue
        role = " ".join(a.get_text(" ", strip=True).split())
        if not role:
            continue  # the logo also links to the job; the text anchor carries the title
        seen.add(href)
        # graduate-job -> a graduate scheme; work-placement-internship -> a
        # placement or internship, decided by the title.
        job_type = (
            "Graduate" if m.group(1) == "graduate-job"
            else infer_type(role, default="Internship")
        )

        card = _card_of(a)
        logo = card.find("img", alt=True) if card else None
        company = (logo.get("alt") or "").strip() if logo else ""
        if not company:
            continue

        # The discipline scope leaks the odd promoted cross-discipline listing
        # (civil, mechanical, the occasional webinar), so I keep only genuine
        # tech roles: a tech keyword must be present and senior or non-tech
        # commercial titles are dropped.
        if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
            continue
        if _NON_COMPUTING_RE.search(role):
            continue
        if not _has_tech_keyword(role.lower()):
            continue

        card_text = " ".join(card.get_text(" ", strip=True).split()) if card else ""
        dl = _DEADLINE_RE.search(card_text)
        loc = _LOCATION_RE.search(card_text)

        if insert_job(ctx, {
            "company":  company,
            "role":     role,
            "type":     job_type,
            "url":      href,
            "location": normalize_location(loc.group(1).strip() if loc else ""),
            "deadline": _parse_deadline(dl.group(1).strip() if dl else ""),
            "source":   "Gradcracker",
        }):
            count += 1
    return count


def scrape_gradcracker(ctx) -> int:
    """Page through each computing-technology listing until a page is empty."""
    print("\nScraping Gradcracker...")
    total = 0
    for path in LISTINGS:
        count = 0
        for page in range(1, 21):
            html = browser_get(f"{BASE}{path}", params={"page": page})
            if not html:
                break
            added = parse_listing(html, ctx)
            count += added
            # A page with no new rows means I have caught up with what the DB
            # already holds or run off the end of the results.
            if added == 0:
                break
        if count:
            print(f"  {path.rsplit('/', 1)[-1]}: {count} new")
        total += count
    print(f"  Gradcracker total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- Gradcracker ---")
    try:
        n = scrape_gradcracker(ctx)
        record_stat(ctx, "Gradcracker", n)
        return n
    except Exception as e:
        print(f"  Error Gradcracker: {e}")
        record_stat(ctx, "Gradcracker", 0, str(e))
        return 0
