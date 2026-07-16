"""Source: jooble."""

import time
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from .. import config
from ..stats import record_stat
from ..http import SESSION

# ─── JOOBLE ──────────────────────────────────────────────────────────────────

def scrape_jooble(ctx) -> int:
    # I use Jooble's POST API which aggregates from hundreds of job boards.
    # JOOBLE_API_KEY must be set as a GitHub Actions secret.
    # Request a free key at jooble.org/api/about.
    api_key = config.JOOBLE_API_KEY
    if not api_key:
        print("  JOOBLE_API_KEY not set - skipping Jooble")
        return 0

    SEARCHES = [
        {"keywords": "software internship", "location": "United Kingdom"},
        {"keywords": "technology intern", "location": "United Kingdom"},
        {"keywords": "year in industry", "location": "United Kingdom"},
        {"keywords": "industrial placement", "location": "United Kingdom"},
        {"keywords": "graduate scheme software", "location": "United Kingdom"},
        {"keywords": "engineering internship", "location": "United Kingdom"},
        # London-targeted passes alongside the UK-wide ones, per the London
        # priority - the UK searches above are untouched.
        {"keywords": "software internship", "location": "London"},
        {"keywords": "technology intern", "location": "London"},
        {"keywords": "industrial placement", "location": "London"},
        {"keywords": "engineering internship", "location": "London"},
        # Embedded and hardware passes, per my placement hunt.
        {"keywords": "embedded internship", "location": "United Kingdom"},
        {"keywords": "electronics placement", "location": "United Kingdom"},
    ]

    count = 0
    for params in SEARCHES:
        try:
            resp = SESSION.post(
                f"https://jooble.org/api/{api_key}",
                json=params,
                headers={"Content-type": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(
                    f"  Jooble HTTP {resp.status_code} for "
                    f"'{params.get('keywords')}'"
                )
                continue

            for job in resp.json().get("jobs", []):
                title = job.get("title", "")
                company = job.get("company", "")
                location = job.get("location", "")
                job_url = job.get("link", "")
                updated = job.get("updated", "")

                if not is_relevant(title, company, location):
                    continue
                if insert_job(ctx, {
                    "company":  company,
                    "role":     title,
                    "type":     infer_type(title),
                    "url":      job_url,
                    "location": normalize_location(location),
                    "source":   "Jooble",
                    "deadline": updated[:10] if updated else None,
                }):
                    count += 1

            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Jooble '{params.get('keywords')}': {e}")

    print(f"  Added {count} from Jooble")
    return count


def run(ctx) -> int:
    print("\n--- Jooble ---")
    n = scrape_jooble(ctx)
    record_stat(ctx, "Jooble", n)
    return n
