"""Source: amazon."""

import time
import requests
from datetime import datetime
from ..db import insert_job
from ..detect import detect_cover_letter_required, detect_sponsors_visa
from ..filters import infer_type, is_relevant
from ..http import HEADERS

# ─── AMAZON JOBS JSON API ─────────────────────────────────────────────────────

def scrape_amazon(existing_keys: set) -> int:
    """Scrape Amazon UK internships via their public JSON search API.

    Amazon hosts their own careers site at amazon.jobs which exposes a
    /en/search.json endpoint - no API key required.
    """
    print("\nScraping Amazon Jobs (UK)...")
    count = 0
    offset = 0
    while offset <= 200:
        try:
            resp = requests.get(
                "https://www.amazon.jobs/en/search.json",
                params={
                    "base_query": "intern",
                    "loc_query":  "United Kingdom",
                    "result_limit": 10,
                    "sort": "relevant",
                    "offset": offset,
                },
                headers={**HEADERS, "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Amazon: HTTP {resp.status_code}")
                break
            data = resp.json()
            jobs = data.get("jobs", [])
            if not jobs:
                break
            for job in jobs:
                title = job.get("title", "")
                country = job.get("country_code", "")
                city = job.get("city", "")
                location = f"{city}, {country}" if city else country
                # I normalise the country code - Amazon uses ISO-3 codes.
                if country not in ("GBR", "IRL"):
                    continue
                job_path = job.get("job_path", "")
                job_url = f"https://www.amazon.jobs{job_path}" if job_path else ""
                description_text = job.get("description", "")
                posted_raw = job.get("posted_date", "")
                # Amazon returns e.g. "January 15, 2026" - convert to ISO.
                opening_date = None
                if posted_raw:
                    try:
                        opening_date = datetime.strptime(
                            posted_raw, "%B %d, %Y"
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                if is_relevant(title, "Amazon", location):
                    if insert_job({
                        "company":               "Amazon",
                        "role":                  title,
                        "type":                  infer_type(title),
                        "url":                   job_url,
                        "location":              location,
                        "source":                "Amazon Jobs",
                        "opening_date":          opening_date,
                        "sponsors_visa":         detect_sponsors_visa(description_text),
                        "cover_letter_required": detect_cover_letter_required(description_text),
                    }, existing_keys):
                        count += 1
            total_hits = data.get("hits", 0)
            if offset + 10 >= total_hits:
                break
            offset += 10
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Amazon offset={offset}: {e}")
            break
    print(f"  Added {count} from Amazon Jobs")
    return count
