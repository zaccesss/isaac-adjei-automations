"""Source: Personio (public XML feed).

Personio tenants publish their whole job list as one keyless XML feed at
/xml on their jobs subdomain: position id, office, department, recruiting
category and name. The role's own page is /job/{id} on the same host. The
seeded list is UK deep-tech; the shared classifier does the filtering.
"""
import re
import time

from ..budget import over_budget
from ..data.companies import PERSONIO_COMPANIES
from ..db import insert_job
from ..filters import is_relevant, is_relevant_job, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat

_POSITION_RE = re.compile(r"<position>(.*?)</position>", re.S)


def _field(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>", block, re.S)
    return (m.group(1).strip() if m else "").replace("&amp;", "&")


def parse_positions(xml: str) -> list[dict]:
    """Return the raw positions in a Personio XML feed as plain dicts."""
    positions = []
    for block in _POSITION_RE.findall(xml):
        positions.append({
            "id":         _field(block, "id"),
            "name":       _field(block, "name"),
            "office":     _field(block, "office"),
            "department": _field(block, "department"),
        })
    return positions


def scrape_personio(ctx, host: str, company_name: str) -> int:
    """Read one Personio tenant's XML feed and keep the UK student tech roles."""
    count = 0
    try:
        resp = SESSION.get(f"https://{host}/xml", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Personio {company_name}: HTTP {resp.status_code}")
            return 0
        positions = parse_positions(resp.text)
    except Exception as e:
        print(f"  Error Personio {company_name}: {e}")
        return 0
    for pos in positions:
        title = pos["name"]
        location = pos["office"]
        job_url = f"https://{host}/job/{pos['id']}" if pos["id"] else ""
        depts = [pos["department"]] if pos["department"] else None
        if is_relevant(title, company_name, location, depts):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     resolve_type(title),
                "url":      job_url,
                "location": location,
                "source":   "Personio",
            }):
                count += 1
        elif is_relevant_job(title, company_name, location):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     "Full-time Job",
                "url":      job_url,
                "location": location,
                "source":   "Personio",
            }):
                count += 1
    if count:
        print(f"  Added {count} from {company_name} (Personio)")
    return count


def run(ctx) -> int:
    print("\n--- Personio ---")
    total = 0
    for host, name in PERSONIO_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Personio companies")
            break
        total += scrape_personio(ctx, host, name)
        time.sleep(0.3)
    record_stat(ctx, "Personio", total)
    return total
