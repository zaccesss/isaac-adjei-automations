"""Source: workday."""

import time
from ..data.companies import PRIORITY_COMPANIES
from ..db import insert_job
from ..filters import infer_type, is_relevant, is_relevant_job
from ..http import HEADERS
from ..locations import is_location_ok
from ..budget import over_budget
from ..stats import record_stat
from ..http import SESSION

# ─── WORKDAY API (NVIDIA, Intel, and other Workday-hosted companies) ─────────

# Confirmed Workday configurations: (subdomain, wdnum, tenant, site_id, display_name)
# Validated against live API - POST to /wday/cxs/{tenant}/{site_id}/jobs.
# ARM, Goldman, JPMorgan, Qualcomm, BAE, Rolls-Royce use Workday but require
# session cookies or proprietary auth - scrape via The Trackr (Playwright) instead.
WORKDAY_COMPANIES = [
    ("nvidia", "5", "nvidia", "NVIDIAExternalCareerSite", "NVIDIA"),
    ("intel",  "1", "intel",  "External",                 "Intel"),
    ("ms",     "5", "ms",     "External",                 "Morgan Stanley"),
]


def scrape_workday(
    ctx, subdomain: str, wdnum: str, tenant: str, site_id: str,
    company_name: str
) -> int:
    """Scrape a Workday-hosted career site via their internal CXS API.

    Workday requires a POST request with JSON body - a plain GET returns 404.
    I page through all results and filter by UK location after retrieval.
    """
    url = (
        f"https://{subdomain}.wd{wdnum}.myworkdayjobs.com"
        f"/wday/cxs/{tenant}/{site_id}/jobs"
    )
    print(f"\nScraping {company_name} Workday...")
    count = 0
    offset = 0
    total = None
    while total is None or offset < total:
        try:
            resp = SESSION.post(
                url,
                json={"limit": 20, "offset": offset, "searchText": "intern"},
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  {company_name} Workday: HTTP {resp.status_code}")
                break
            data = resp.json()
            if total is None:
                total = data.get("total", 0)
            jobs = data.get("jobPostings", [])
            if not jobs:
                break
            for job in jobs:
                title = job.get("title", "")
                # Workday location is in 'locationsText' or the first bulletField.
                location_text = job.get("locationsText", "") or ""
                if not location_text:
                    for bf in job.get("bulletFields", []):
                        if bf:
                            location_text = bf
                            break
                # I pre-filter non-UK roles to avoid HEAD-checking hundreds of
                # US job URLs. is_relevant does a second check inside.
                is_priority = any(p in company_name.lower() for p in PRIORITY_COMPANIES)
                if location_text and not is_location_ok(location_text, is_priority):
                    continue
                ext_url = job.get("externalPath", "")
                job_url = (
                    f"https://{subdomain}.wd{wdnum}.myworkdayjobs.com"
                    f"/en-US/{site_id}/job{ext_url}"
                ) if ext_url else ""
                if is_relevant(title, company_name, location_text):
                    if insert_job(ctx, {
                        "company":  company_name,
                        "role":     title,
                        "type":     infer_type(title),
                        "url":      job_url,
                        "location": location_text,
                        "source":   "Workday",
                    }):
                        count += 1
                elif is_relevant_job(title, company_name, location_text):
                    if insert_job(ctx, {
                        "company":  company_name,
                        "role":     title,
                        "type":     "Full-time Job",
                        "url":      job_url,
                        "location": location_text,
                        "source":   "Workday",
                    }):
                        count += 1
            offset += len(jobs)
            time.sleep(0.5)
            if len(jobs) < 20:
                break
        except Exception as e:
            print(f"  Error {company_name} Workday offset={offset}: {e}")
            break
    print(f"  Added {count} from {company_name} Workday")
    return count


def run(ctx) -> int:
    print("\n--- Workday (NVIDIA / Intel / Morgan Stanley) ---")
    total = 0
    for subdomain, wdnum, tenant, site_id, name in WORKDAY_COMPANIES:
        if over_budget(ctx):
            break
        try:
            total += scrape_workday(ctx, subdomain, wdnum, tenant, site_id, name)
        except Exception as e:
            print(f"  Error {name} Workday: {e}")
    record_stat(ctx, "Workday", total)
    return total
