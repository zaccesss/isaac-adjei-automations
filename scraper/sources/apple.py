"""Source: apple."""

import time
import json
import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..http import HEADERS
from ..stats import record_stat

# ─── APPLE CAREERS ──────────────────────────────────────────────────────────

def scrape_apple(ctx) -> int:
    """Scrape Apple UK internships via their public jobs search API."""
    print("\nScraping Apple Careers (UK)...")
    count = 0
    page = 1
    while page <= 10:
        try:
            resp = requests.get(
                "https://jobs.apple.com/api/role/search",
                params={
                    "filters": json.dumps({
                        "postingpostLocation": ["postLocation-GBR"],
                        "employmentType": ["INTERNS"],
                    }),
                    "page": str(page),
                    "locale": "en-US",
                },
                headers={**HEADERS, "Referer": "https://jobs.apple.com/"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Apple: HTTP {resp.status_code}")
                break
            data = resp.json()
            results = data.get("searchResults", [])
            if not results:
                break
            for role in results:
                title = role.get("postingTitle", "")
                locs = role.get("locations", [])
                location = locs[0].get("name", "") if locs else ""
                pid = role.get("positionId", "")
                job_url = (
                    f"https://jobs.apple.com/en-gb/details/{pid}"
                    if pid else ""
                )
                if not is_relevant(title, "Apple", location):
                    continue
                if insert_job(ctx, {
                    "company":  "Apple",
                    "role":     title,
                    "type":     infer_type(title),
                    "url":      job_url,
                    "location": location,
                    "source":   "Apple Careers",
                }):
                    count += 1
            if len(results) < 20:
                break
            page += 1
            time.sleep(1)
        except Exception as e:
            print(f"  Error Apple p{page}: {e}")
            break
    print(f"  Added {count} from Apple Careers")
    return count


def run(ctx) -> int:
    print("\n--- Apple Careers ---")
    try:
        n = scrape_apple(ctx)
        record_stat(ctx, "Apple Careers", n)
        return n
    except Exception as e:
        print(f"  Error Apple: {e}")
        record_stat(ctx, "Apple Careers", 0, str(e))
        return 0
