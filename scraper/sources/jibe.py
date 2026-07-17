"""Source: Jibe/iCIMS careers API.

Jibe is iCIMS's careers-site CMS; its sites expose a keyless /api/jobs JSON
endpoint that pages through every posting with title, location, employment
type, description and the specific apply URL. I scope every query to the UK
so a global employer's worldwide fabs never flood the table.
"""
import time

from ..budget import over_budget
from ..data.companies import JIBE_COMPANIES
from ..db import insert_job
from ..detect import _strip_html, detect_cover_letter_required, detect_sponsors_visa
from ..filters import is_relevant, is_relevant_job, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat


def scrape_jibe(ctx, host: str, company_name: str) -> int:
    """Page one Jibe careers site's UK postings and keep the student tech roles."""
    count = 0
    page = 1
    while page <= 10:
        try:
            resp = SESSION.get(
                f"https://{host}/api/jobs",
                params={"location": "United Kingdom", "page": page},
                headers={**HEADERS, "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Jibe {company_name}: HTTP {resp.status_code}")
                break
            jobs = resp.json().get("jobs", [])
        except Exception as e:
            print(f"  Error Jibe {company_name} page={page}: {e}")
            break
        if not jobs:
            break
        for wrapper in jobs:
            job = wrapper.get("data", {})
            title = job.get("title", "")
            location = job.get("full_location") or job.get("country") or ""
            # The apply URL lands on the login step of the application; the
            # bare job page is the same URL without that suffix.
            job_url = (job.get("apply_url") or "").removesuffix("/login")
            description = _strip_html(job.get("description", ""))
            extra = {
                "sponsors_visa":         detect_sponsors_visa(description),
                "cover_letter_required": detect_cover_letter_required(description),
                "description":           description,
            }
            if is_relevant(title, company_name, location):
                if insert_job(ctx, {
                    "company":  company_name,
                    "role":     title,
                    "type":     resolve_type(title),
                    "url":      job_url,
                    "location": location,
                    "source":   "Jibe",
                    **extra,
                }):
                    count += 1
            elif is_relevant_job(title, company_name, location):
                if insert_job(ctx, {
                    "company":  company_name,
                    "role":     title,
                    "type":     "Full-time Job",
                    "url":      job_url,
                    "location": location,
                    "source":   "Jibe",
                    **extra,
                }):
                    count += 1
        if len(jobs) < 10:
            break
        page += 1
        time.sleep(0.4)
    if count:
        print(f"  Added {count} from {company_name} (Jibe)")
    return count


def run(ctx) -> int:
    print("\n--- Jibe (iCIMS careers) ---")
    total = 0
    for host, name in JIBE_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Jibe companies")
            break
        total += scrape_jibe(ctx, host, name)
    record_stat(ctx, "Jibe", total)
    return total
