"""Source: adzuna."""

import time
import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from .. import config
from ..stats import record_stat

# ─── ADZUNA ──────────────────────────────────────────────────────────────────

def scrape_adzuna(ctx) -> int:
    # I use Adzuna's aggregated UK jobs API which covers hundreds of job boards.
    # ADZUNA_APP_ID and ADZUNA_APP_KEY must be set as GitHub Actions secrets.
    # Register free at developer.adzuna.com - 1000 requests/month on trial.
    app_id = config.ADZUNA_APP_ID
    app_key = config.ADZUNA_APP_KEY
    if not app_id or not app_key:
        print("  ADZUNA_APP_ID/ADZUNA_APP_KEY not set - skipping Adzuna")
        return 0

    BASE = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    # Each search carries its own "where". The UK-wide set stays as it was; a
    # London-targeted set rides alongside so the results lean London without
    # losing national coverage. 20 requests/day sits well inside the 1000/month
    # trial quota.
    SEARCHES = [
        {"what": "software intern", "where": "UK"},
        {"what": "technology internship", "where": "UK"},
        {"what": "engineering internship", "where": "UK"},
        {"what": "year in industry", "where": "UK"},
        {"what": "industrial placement", "where": "UK"},
        {"what": "graduate scheme technology", "where": "UK"},
        {"what": "data science internship", "where": "UK"},
        {"what": "machine learning internship", "where": "UK"},
        {"what": "embedded software intern", "where": "UK"},
        {"what": "firmware engineer intern", "where": "UK"},
        {"what": "cloud engineer internship", "where": "UK"},
        {"what": "devops internship", "where": "UK"},
        {"what": "cyber security intern", "where": "UK"},
        {"what": "quant developer internship", "where": "UK"},
        {"what": "software intern", "where": "London"},
        {"what": "technology internship", "where": "London"},
        {"what": "engineering internship", "where": "London"},
        {"what": "industrial placement", "where": "London"},
        {"what": "data science internship", "where": "London"},
        {"what": "machine learning internship", "where": "London"},
    ]

    def _resolve_url(tracking_url: str) -> str:
        # I follow the Adzuna redirect to get the actual company/ATS URL.
        # If it still lands on adzuna.co.uk the tracking link is kept as fallback.
        try:
            r = requests.head(tracking_url, allow_redirects=True, timeout=5)
            if r.url and "adzuna" not in r.url:
                return r.url
        except Exception:
            pass
        return tracking_url

    count = 0
    for search in SEARCHES:
        what = search["what"]
        try:
            resp = requests.get(
                BASE,
                params={
                    "app_id":           app_id,
                    "app_key":          app_key,
                    "what":             what,
                    "where":            search["where"],
                    "results_per_page": 15,
                    "content-type":     "application/json",
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Adzuna HTTP {resp.status_code} for '{what}' ({search['where']})")
                continue

            for job in resp.json().get("results", []):
                title = job.get("title", "")
                company = (job.get("company") or {}).get("display_name", "")
                location = (
                    (job.get("location") or {})
                    .get("display_name", "")
                )
                job_url = _resolve_url(job.get("redirect_url", ""))
                expiry = job.get("expiration_date", "")

                if not is_relevant(title, company, location):
                    continue
                if insert_job(ctx, {
                    "company":  company,
                    "role":     title,
                    "type":     infer_type(title),
                    "url":      job_url,
                    "location": normalize_location(location),
                    "source":   "Adzuna",
                    "deadline": expiry[:10] if expiry else None,
                    "description": job.get("description", ""),
                }):
                    count += 1

            time.sleep(1.0)
        except Exception as e:
            print(f"  Error Adzuna '{what}': {e}")

    print(f"  Added {count} from Adzuna")
    return count


def run(ctx) -> int:
    print("\n--- Adzuna ---")
    n = scrape_adzuna(ctx)
    record_stat(ctx, "Adzuna", n)
    return n
