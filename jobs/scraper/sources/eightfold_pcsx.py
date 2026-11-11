"""Source: Eightfold careers sites on the PCSX search endpoint.

Some Eightfold tenants refuse the older /api/apply/v2/jobs endpoint the eightfold
source reads ("Not authorized for PCSX") and answer only the newer search at
/api/pcsx/search on their own careers domain, which robots.txt allows. A location
filter keeps the read to UK roles. Added November 2026 for the UKESF partner
companies; every employer here is capped and guarded as a newer source.
"""
import time

from ..budget import over_budget
from ..db import insert_job
from ..filters import passes_new_source_guard, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat

# (careers_host, eightfold_domain, display_name), each checked live November 2026
PCSX_COMPANIES = [
    ("jobs.infineon.com", "infineon.com", "Infineon"),
    ("careers.qualcomm.com", "qualcomm.com", "Qualcomm"),
]

_PAGE = 10
_MAX_RESULTS = 100


def parse_positions(payload: dict, host: str) -> list[dict]:
    """The positions in one search page as plain dicts: title, url, location and department."""
    data = payload.get("data") or {}
    jobs = []
    for pos in data.get("positions") or []:
        path = pos.get("positionUrl") or ""
        places = pos.get("standardizedLocations") or pos.get("locations") or []
        jobs.append({
            "title":    (pos.get("name") or "").strip(),
            "url":      f"https://{host}{path}" if path.startswith("/") else path,
            "location": "; ".join(p for p in places if p),
            "depts":    [pos["department"]] if pos.get("department") else None,
        })
    return jobs


def scrape_pcsx(ctx, host: str, domain: str, company_name: str) -> int:
    count = 0
    start = 0
    total = None
    while start < _MAX_RESULTS and (total is None or start < total):
        try:
            resp = SESSION.get(
                f"https://{host}/api/pcsx/search",
                params={"domain": domain, "query": "", "location": "United Kingdom", "start": start},
                headers={**HEADERS, "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                # a 429 means the site is rate limiting; the next run tries again
                print(f"  Eightfold PCSX {company_name}: HTTP {resp.status_code}")
                break
            payload = resp.json()
        except Exception as e:
            print(f"  Error Eightfold PCSX {company_name}: {e}")
            break
        if total is None:
            total = (payload.get("data") or {}).get("count") or 0
        jobs = parse_positions(payload, host)
        if not jobs:
            break
        for job in jobs:
            if not passes_new_source_guard(job["title"], company_name, job["location"], None, job["depts"]):
                continue
            if insert_job(ctx, {
                "company":  company_name,
                "role":     job["title"],
                "type":     resolve_type(job["title"]),
                "url":      job["url"],
                "location": job["location"],
                "source":   "Eightfold",
                "cap_key":  company_name,
            }):
                count += 1
        start += len(jobs)
        time.sleep(1)
    if count:
        print(f"  Added {count} from {company_name} (Eightfold PCSX)")
    return count


def run(ctx) -> int:
    print("\n--- Eightfold PCSX ---")
    total = 0
    for host, domain, name in PCSX_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Eightfold PCSX companies")
            break
        total += scrape_pcsx(ctx, host, domain, name)
    record_stat(ctx, "Eightfold PCSX", total)
    return total
