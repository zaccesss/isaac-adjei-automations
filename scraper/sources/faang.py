"""Source: FAANG+ careers that need a rendered browser.

Goldman Sachs runs a JavaScript careers app whose backing fetch is obfuscated, so
there is no clean JSON to read; I render the results page with Scrapling's Camoufox
browser - which also clears the bot wall that made the old Playwright scraper return
zero - and read the job cards out of the populated DOM.

Google and Meta are deliberately left out: Google's results app serves the job list
only intermittently to an automated browser (it more often renders empty), and Meta
keeps its listings behind a Relay GraphQL query whose persisted id rotates. Both
would be fragile, and their internships already arrive through the Trackr. JPMorgan
is on Oracle Recruiting Cloud and lives in the oracle_ce source, not here.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, resolve_type
from ..http_browser import browser_render
from ..locations import is_location_ok, normalize_location
from ..stats import record_stat

GOLDMAN_BASE = "https://higher.gs.com"

_GOLDMAN_JOB_RE = re.compile(r"/roles/\d+")
_UK_RE = re.compile(r"United Kingdom|London|Birmingham|Manchester|Edinburgh|Glasgow|Reading|Cambridge|\bUK\b", re.I)


def _card_text(anchor) -> str:
    node = anchor
    for _ in range(4):
        node = node.parent if node.parent else node
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _keep(role: str) -> bool:
    """Only genuine tech roles, no senior or commercial titles."""
    if not role or _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
        return False
    return _has_tech_keyword(role.lower())


def scrape_goldman(ctx) -> int:
    """Render Goldman's roles results and read the UK tech cards."""
    count = 0
    seen: set[str] = set()
    for page in range(1, 6):
        html = browser_render(f"{GOLDMAN_BASE}/roles", {"page": page})
        if not html:
            break
        anchors = [
            a for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)
            if _GOLDMAN_JOB_RE.search(a["href"])
        ]
        new = 0
        for a in anchors:
            href = urljoin(GOLDMAN_BASE, a["href"].split("?")[0])
            if href in seen:
                continue
            seen.add(href)
            role = " ".join(a.get_text(" ", strip=True).split())
            if not _keep(role):
                continue
            text = _card_text(a)
            # Goldman lists every region, so I keep only UK cards and read the
            # "City - Country" pair out of the card.
            if not _UK_RE.search(text):
                continue
            loc = re.search(r"([A-Z][a-zA-Z]+)\s*[·|]\s*(United Kingdom)", text)
            location = f"{loc.group(1)}, United Kingdom" if loc else "United Kingdom"
            if not is_location_ok(location, False):
                continue
            if insert_job(ctx, {
                "company":  "Goldman Sachs",
                "role":     role,
                "type":     resolve_type(role, fallback="Graduate"),
                "url":      href,
                "location": normalize_location(location),
                "source":   "Goldman Sachs",
            }):
                count += 1
                new += 1
        if new == 0:
            break
    return count



def run(ctx) -> int:
    print("\n--- FAANG+ (rendered) ---")
    total = 0
    for name, fn in (("Goldman Sachs", scrape_goldman),):
        try:
            n = fn(ctx)
            if n:
                print(f"  {name}: {n} new")
            total += n
        except Exception as e:
            print(f"  Error {name}: {e}")
    record_stat(ctx, "FAANG+ rendered", total)
    return total
