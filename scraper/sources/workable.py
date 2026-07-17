"""Source: Workable (public widget API).

Workable hosts the small UK deep-tech startups - defence AI, satcom terminals,
power electronics - that never post on the big boards. Its careers widget is
backed by a public JSON endpoint that needs no key: one GET per company returns
every published job with its title, department, employment type and location,
plus the specific application URL. I read the seeded company list and keep only
UK student tech roles with the shared classifier.
"""
import time

from ..budget import over_budget
from ..data.companies import WORKABLE_COMPANIES
from ..db import insert_job
from ..filters import is_relevant, is_relevant_job, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat


def _location(job: dict) -> str:
    """Build a readable location from the widget's split fields."""
    parts = [job.get("city") or "", job.get("country") or ""]
    loc = ", ".join(p for p in parts if p)
    if not loc and job.get("telecommuting"):
        loc = "Remote"
    return loc


def scrape_workable(ctx, slug: str, company_name: str) -> int:
    """Read one Workable tenant's published jobs and keep the UK student tech roles."""
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    count = 0
    try:
        resp = SESSION.get(
            url,
            params={"details": "false"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  Workable {company_name}: HTTP {resp.status_code}")
            return 0
        jobs = resp.json().get("jobs", [])
    except Exception as e:
        print(f"  Error Workable {company_name}: {e}")
        return 0
    for job in jobs:
        title = job.get("title", "")
        location = _location(job)
        job_url = job.get("url") or job.get("application_url") or ""
        depts = [job.get("department", "")] if job.get("department") else None
        if is_relevant(title, company_name, location, depts):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     resolve_type(title),
                "url":      job_url,
                "location": location,
                "source":   "Workable",
            }):
                count += 1
        elif is_relevant_job(title, company_name, location):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     "Full-time Job",
                "url":      job_url,
                "location": location,
                "source":   "Workable",
            }):
                count += 1
    if count:
        print(f"  Added {count} from {company_name} (Workable)")
    return count


def run(ctx) -> int:
    print("\n--- Workable ---")
    total = 0
    for slug, name in WORKABLE_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Workable companies")
            break
        total += scrape_workable(ctx, slug, name)
        time.sleep(0.3)
    record_stat(ctx, "Workable", total)
    return total
