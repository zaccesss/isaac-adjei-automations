"""Source: reed."""

import time
import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from .. import config
from ..stats import record_stat

# ─── REED.CO.UK ─────────────────────────────────────────────────────────────

def scrape_reed(ctx) -> int:
    # I use Reed's public API - REED_API_KEY must be set as a GitHub Actions
    # secret. Register free at reed.co.uk/developers/jobseeker to get one.
    api_key = config.REED_API_KEY
    if not api_key:
        print("  REED_API_KEY not set - skipping Reed.co.uk")
        return 0

    # I run separate searches for each role type so I can use the graduate flag
    # and get broader keyword coverage than a single broad query.
    SEARCHES = [
        {"keywords": "software intern",
         "locationName": "United Kingdom"},
        {"keywords": "technology internship",
         "locationName": "United Kingdom"},
        {"keywords": "engineering internship",
         "locationName": "United Kingdom"},
        {"keywords": "data science internship",
         "locationName": "United Kingdom"},
        {"keywords": "year in industry",
         "locationName": "United Kingdom"},
        {"keywords": "industrial placement",
         "locationName": "United Kingdom"},
        # I use graduate=true for these so Reed pre-filters to graduate roles.
        {"keywords": "software engineer",
         "locationName": "United Kingdom", "graduate": "true"},
        {"keywords": "technology",
         "locationName": "United Kingdom", "graduate": "true"},
        # London-targeted passes ride alongside the UK-wide ones (20 mile radius
        # covers Greater London), so results lean London without losing national
        # coverage.
        {"keywords": "software intern",
         "locationName": "London", "distanceFromLocation": 20},
        {"keywords": "technology internship",
         "locationName": "London", "distanceFromLocation": 20},
        {"keywords": "engineering internship",
         "locationName": "London", "distanceFromLocation": 20},
        {"keywords": "industrial placement",
         "locationName": "London", "distanceFromLocation": 20},
        {"keywords": "year in industry",
         "locationName": "London", "distanceFromLocation": 20},
    ]

    count = 0
    for params in SEARCHES:
        try:
            resp = requests.get(
                "https://www.reed.co.uk/api/1.0/search",
                params={**params, "resultsToTake": 100},
                auth=(api_key, ""),
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Reed HTTP {resp.status_code} for {params}")
                continue

            for job in resp.json().get("results", []):
                title = job.get("jobTitle", "")
                company = job.get("employerName", "")
                location = job.get("locationName", "")
                job_id = job.get("jobId", "")
                job_url = (
                    f"https://www.reed.co.uk/jobs/{job_id}"
                    if job_id else ""
                )
                expiry = job.get("expirationDate", "")

                if not is_relevant(title, company, location):
                    continue
                if insert_job(ctx, {
                    "company":  company,
                    "role":     title,
                    "type":     infer_type(title),
                    "url":      job_url,
                    "location": normalize_location(location),
                    "source":   "Reed",
                    "deadline": expiry,
                    "description": job.get("jobDescription", ""),
                }):
                    count += 1

            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Reed {params.get('keywords')}: {e}")

    print(f"  Added {count} from Reed.co.uk")
    return count


def run(ctx) -> int:
    print("\n--- Reed ---")
    n = scrape_reed(ctx)
    record_stat(ctx, "Reed", n)
    return n
