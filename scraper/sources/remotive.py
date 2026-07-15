"""Source: remotive."""

import time
from ..db import insert_job
from ..filters import is_relevant_job
from ..http import HEADERS
from ..stats import record_stat
from ..http import SESSION

# ─── REMOTIVE (remote full-time tech jobs, worldwide) ────────────────────────

def scrape_remotive(ctx) -> int:
    # I use Remotive's free public API which returns currently open remote jobs.
    # I filter to full_time only so internship/contract listings are excluded.
    print("\nScraping Remotive (remote full-time jobs)...")
    count = 0
    categories = ["software-dev", "devops-sysadmin", "data", "product"]
    seen_ids: set = set()
    for cat in categories:
        url = f"https://remotive.com/api/remote-jobs?category={cat}&limit=100"
        try:
            resp = SESSION.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  Remotive {cat}: HTTP {resp.status_code}")
                continue
            for job in resp.json().get("jobs", []):
                job_id = job.get("id")
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                if job.get("job_type") != "full_time":
                    continue
                title = job.get("title", "")
                company = job.get("company_name", "")
                job_url = job.get("url", "")
                location = job.get("candidate_required_location", "")
                salary = job.get("salary", "")
                pub_str = (job.get("publication_date") or "")[:10] or None
                if not is_relevant_job(title, company, location):
                    continue
                if insert_job(ctx, {
                    "company":      company,
                    "role":         title,
                    "type":         "Full-time Job",
                    "url":          job_url,
                    "location":     location,
                    "salary_range": salary or "",
                    "opening_date": pub_str,
                    "source":       "Remotive",
                }):
                    count += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Remotive {cat}: {e}")
    print(f"  Added {count} from Remotive")
    return count


def run(ctx) -> int:
    # The old main called Remotive without a section header; kept that way.
    n = scrape_remotive(ctx)
    record_stat(ctx, "Remotive", n)
    return n
