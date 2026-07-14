"""Source: smartrecruiters."""

import time
import requests
from ..db import insert_job
from ..filters import infer_type, is_relevant
from ..http import HEADERS

# ─── SMARTRECRUITERS ─────────────────────────────────────────────────────────

def scrape_smartrecruiters(
    company_id: str, company_name: str, existing_keys: set
) -> int:
    """SmartRecruiters public API - used by KPMG, Vodafone and others.

    I use the v1 postings endpoint with limit=100 because SmartRecruiters
    defaults to a smaller page size and many large employers have hundreds
    of open roles.
    """
    url = (
        f"https://api.smartrecruiters.com/v1/companies"
        f"/{company_id}/postings?limit=100"
    )
    count = 0
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(
                f"  SmartRecruiters {company_name}: "
                f"HTTP {resp.status_code}"
            )
            return 0

        for job in resp.json().get("content", []):
            title = job.get("name", "")
            # I try city first then country as a fallback because many UK
            # employers set city not country.
            location = (
                job.get("location", {}).get("city", "")
                or job.get("location", {}).get("country", "")
            )
            # I construct the URL from company_id and job_id because
            # SmartRecruiters does not always include a direct link in
            # the API response.
            job_url = (
                f"https://jobs.smartrecruiters.com"
                f"/{company_id}/{job.get('id', '')}"
            )

            if not is_relevant(title, company_name, location):
                continue

            if insert_job({
                "company":  company_name,
                "role":     title,
                "type":     infer_type(title),
                "url":      job_url,
                "location": location,
                "source":   "SmartRecruiters",
            }, existing_keys):
                count += 1

        time.sleep(0.5)
    except Exception as e:
        print(f"  Error SmartRecruiters {company_name}: {e}")
    return count
