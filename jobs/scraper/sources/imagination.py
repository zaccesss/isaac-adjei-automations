"""Source: Imagination Technologies (PageUp RSS feed).

Imagination's careers site runs on PageUp, which publishes every open role as one
keyless RSS feed. Each item carries the title, the role's own page and PageUp's
job: fields for location, closing date and work type. The work type ("Early
Career") marks the graduate roles whose titles carry no student term.
Added November 2026; capped and guarded as a newer source.
"""
import xml.etree.ElementTree as ET
from datetime import datetime

from ..db import insert_job, plain_date
from ..filters import passes_new_source_guard, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat

FEED = "https://careers.pageuppeople.com/774/cw/en/rss"
COMPANY = "Imagination Technologies"
_NS = {"job": "http://pageuppeople.com/"}


def _closing_date(value: str) -> "str | None":
    """An ISO date from PageUp's closing date, which may be ISO, dd/mm/yyyy or an RFC 822 stamp."""
    value = (value or "").strip()
    if not value:
        return None
    iso = plain_date(value)
    if iso:
        return iso
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S Z", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_feed(xml_text: str) -> list[dict]:
    """The feed's items as plain dicts: title, url, location, closing date and work types."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    items = []
    for item in root.iter("item"):
        work_type = item.findtext("job:workType", default="", namespaces=_NS) or ""
        items.append({
            "title":    (item.findtext("title") or "").strip(),
            "url":      (item.findtext("link") or "").strip(),
            "location": (item.findtext("job:location", default="", namespaces=_NS) or "").strip(),
            "closing":  _closing_date(item.findtext("job:closingDate", default="", namespaces=_NS) or ""),
            "work_types": [w.strip() for w in work_type.split(",") if w.strip()],
        })
    return items


def scrape_imagination(ctx) -> int:
    resp = SESSION.get(FEED, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"  Imagination: HTTP {resp.status_code}")
        return 0
    count = 0
    for job in parse_feed(resp.content):
        # the work type stands in for a department, so "Early Career" counts as a student signal
        if not passes_new_source_guard(job["title"], COMPANY, job["location"], job["closing"], job["work_types"]):
            continue
        if insert_job(ctx, {
            "company":  COMPANY,
            "role":     job["title"],
            "type":     resolve_type(job["title"], fallback="Graduate"),
            "url":      job["url"],
            "location": job["location"],
            "deadline": job["closing"],
            "source":   "Imagination Careers",
            "cap_key":  COMPANY,
        }):
            count += 1
    if count:
        print(f"  Added {count} from {COMPANY}")
    return count


def run(ctx) -> int:
    print("\n--- Imagination Technologies ---")
    try:
        n = scrape_imagination(ctx)
        record_stat(ctx, "Imagination Careers", n)
        return n
    except Exception as e:
        print(f"  Error Imagination: {e}")
        record_stat(ctx, "Imagination Careers", 0, str(e))
        return 0
