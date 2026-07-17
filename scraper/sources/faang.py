"""Source: FAANG+ careers that need more than a plain API call.

Goldman Sachs runs a JavaScript careers app whose backing fetch is obfuscated, so
there is no clean JSON to read; I render the results page with Scrapling's Camoufox
browser - which also clears the bot wall that made the old Playwright scraper return
zero - and read the job cards out of the populated DOM.

JPMorgan runs on Oracle Recruiting Cloud, whose REST API is reachable with a plain
request once the expand parameter is supplied, so it needs no browser at all.

Google and Meta are deliberately left out: Google's results app serves the job list
only intermittently to an automated browser (it more often renders empty), and Meta
keeps its listings behind a Relay GraphQL query whose persisted id rotates. Both
would be fragile, and their internships already arrive through the Trackr.
"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, resolve_type
from ..http import HEADERS, SESSION
from ..http_browser import browser_render
from ..locations import is_location_ok, normalize_location
from ..stats import record_stat

GOLDMAN_BASE = "https://higher.gs.com"
# JPMorgan runs on Oracle Recruiting Cloud, whose public REST API needs no browser
# once the expand parameter is supplied (without it the keyword search returns a
# count but an empty list). The UI job page hangs off the same site number.
JPM_API = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
JPM_JOB = "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job"

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


def scrape_jpmorgan(ctx) -> int:
    """Read JPMorgan's Oracle jobs API and keep the UK early-careers tech roles."""
    count = 0
    seen: set[str] = set()
    for keyword in ("intern", "graduate", "apprentice", "placement"):
        for offset in range(0, 120, 10):
            finder = (
                f'findReqs;siteNumber=CX_1001,keyword="{keyword}",'
                f"limit=10,offset={offset},sortBy=POSTING_DATES_DESC"
            )
            try:
                resp = SESSION.get(
                    JPM_API,
                    params={
                        "onlyData": "true",
                        "expand": "requisitionList.workLocation",
                        "finder": finder,
                    },
                    headers={**HEADERS, "Accept": "application/json"},
                    timeout=20,
                )
                if resp.status_code != 200:
                    break
                items = resp.json().get("items", [])
                reqs = items[0].get("requisitionList", []) if items else []
            except Exception as e:
                print(f"  JPMorgan {keyword} offset={offset}: {e}")
                break
            if not reqs:
                break
            for job in reqs:
                role = (job.get("Title") or "").strip()
                location = (job.get("PrimaryLocation") or "").strip()
                jid = job.get("Id") or ""
                if not role or not jid or "United Kingdom" not in location:
                    continue
                if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                    continue
                if not _has_tech_keyword(role.lower()):
                    continue
                url = f"{JPM_JOB}/{jid}"
                if url in seen:
                    continue
                seen.add(url)
                if insert_job(ctx, {
                    "company":  "JPMorgan Chase",
                    "role":     role,
                    "type":     resolve_type(role, fallback="Internship"),
                    "url":      url,
                    "location": normalize_location(location),
                    "source":   "JPMorgan",
                }):
                    count += 1
    return count


def run(ctx) -> int:
    print("\n--- FAANG+ (rendered) ---")
    total = 0
    for name, fn in (("Goldman Sachs", scrape_goldman), ("JPMorgan", scrape_jpmorgan)):
        try:
            n = fn(ctx)
            if n:
                print(f"  {name}: {n} new")
            total += n
        except Exception as e:
            print(f"  Error {name}: {e}")
    record_stat(ctx, "FAANG+ rendered", total)
    return total
