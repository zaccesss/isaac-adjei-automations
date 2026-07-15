"""Source: jobicy."""

import time
from ..data.keywords import TECH_KEYWORDS
from ..db import insert_job
from ..filters import infer_type, is_student_role
from ..stats import record_stat
from ..http import SESSION

# ─── JOBICY ──────────────────────────────────────────────────────────────────

def scrape_jobicy(ctx) -> int:
    # I use Jobicy's free open API - no auth required.
    # It covers remote-only tech roles so I skip the location check and accept
    # any matching student role since "Remote" is UK-acceptable.
    QUERIES = [
        {"industry": "engineering", "tag": "intern"},
        {"industry": "software-development", "tag": "intern"},
        {"industry": "data-science", "tag": "intern"},
    ]

    count = 0
    for params in QUERIES:
        try:
            resp = SESSION.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={**params, "count": 50},
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            for job in resp.json().get("jobs", []):
                title = job.get("jobTitle", "")
                company = job.get("companyName", "")
                job_url = job.get("url", "")

                # I skip the location check here because Jobicy is remote-only;
                # I still require a student term and tech keyword.
                if not is_student_role(title):
                    continue
                if not any(k in title.lower() for k in TECH_KEYWORDS):
                    continue
                if insert_job(ctx, {
                    "company":  company,
                    "role":     title,
                    "type":     infer_type(title),
                    "url":      job_url,
                    "location": "Remote",
                    "source":   "Jobicy",
                }):
                    count += 1

            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Jobicy: {e}")

    print(f"  Added {count} from Jobicy")
    return count


def run(ctx) -> int:
    print("\n--- Jobicy ---")
    n = scrape_jobicy(ctx)
    record_stat(ctx, "Jobicy", n)
    return n
