"""Source: lever."""

import time
import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant, is_relevant_job
from ..http import HEADERS

def fetch_lever_details(slug: str, posting_id: str) -> dict:
    """Call the Lever individual posting endpoint for extra fields.

    Lever's list API sometimes omits location at the top level. The single
    posting endpoint returns the same structure but can have additional
    fields populated - I extract location and any workplaceType hint.
    """
    url = f"https://api.lever.co/v0/postings/{slug}/{posting_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("categories", {}).get("location", "")
            wt  = data.get("workplaceType", "")
            return {"location": loc, "work_mode": wt}
    except Exception:
        pass
    return {}


# ─── LEVER JSON API ─────────────────────────────────────────────────────────

def scrape_lever(
    slug: str, company_name: str, existing_keys: set
) -> int:
    # I use Lever's v0 public postings endpoint which returns all jobs as a
    # flat JSON array. mode=json returns structured data not an HTML page.
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    count = 0
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Lever {company_name}: HTTP {resp.status_code}")
            return 0

        for job in resp.json():
            # I use "text" because Lever calls it that rather than "title".
            title = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            work_mode = job.get("workplaceType", "")
            # I prefer hostedUrl over applyUrl because it shows the full JD.
            job_url = job.get("hostedUrl", "")
            posting_id = job.get("id", "")
            # I call the detail endpoint when location is empty because
            # Lever's listing API sometimes omits the location field.
            if not location and posting_id:
                extra = fetch_lever_details(slug, posting_id)
                location = extra.get("location", "")
                work_mode = work_mode or extra.get("work_mode", "")
                if location:
                    time.sleep(0.2)

            if is_relevant(title, company_name, location):
                if insert_job({
                    "company":   company_name,
                    "role":      title,
                    "type":      infer_type(title),
                    "url":       job_url,
                    "location":  location,
                    "work_mode": work_mode,
                    "source":    "Lever",
                }, existing_keys):
                    count += 1
            elif is_relevant_job(title, company_name, location):
                if insert_job({
                    "company":   company_name,
                    "role":      title,
                    "type":      "Full-time Job",
                    "url":       job_url,
                    "location":  location,
                    "work_mode": work_mode,
                    "source":    "Lever",
                }, existing_keys):
                    count += 1

        time.sleep(0.5)
    except Exception as e:
        print(f"  Error Lever {company_name}: {e}")
    return count
