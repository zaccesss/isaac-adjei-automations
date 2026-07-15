"""Source: arbeitnow."""

import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from ..stats import record_stat

# ─── ARBEITNOW ───────────────────────────────────────────────────────────────

def scrape_arbeitnow(ctx) -> int:
    # I use Arbeitnow's free public API - no auth required.
    # It aggregates European tech jobs and is particularly strong for remote
    # and EU-based engineering roles.
    count = 0
    try:
        resp = requests.get(
            "https://arbeitnow.com/api/job-board-api",
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  Arbeitnow HTTP {resp.status_code}")
            return 0

        for job in resp.json().get("data", []):
            title = job.get("title", "")
            company = job.get("company_name", "")
            location = job.get("location", "")
            job_url = job.get("url", "")
            remote = job.get("remote", False)
            if remote and not location:
                location = "Remote"

            if not is_relevant(title, company, location):
                continue
            if insert_job(ctx, {
                "company":  company,
                "role":     title,
                "type":     infer_type(title),
                "url":      job_url,
                "location": normalize_location(location),
                "source":   "Arbeitnow",
            }):
                count += 1

    except Exception as e:
        print(f"  Error Arbeitnow: {e}")

    print(f"  Added {count} from Arbeitnow")
    return count


def run(ctx) -> int:
    print("\n--- Arbeitnow ---")
    n = scrape_arbeitnow(ctx)
    record_stat(ctx, "Arbeitnow", n)
    return n
