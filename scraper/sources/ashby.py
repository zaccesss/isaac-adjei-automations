"""Source: ashby."""

import time
from ..db import insert_job
from ..detect import detect_cover_letter_required, detect_sponsors_visa
from ..filters import resolve_type, is_relevant, is_relevant_job
from ..http import HEADERS
from ..budget import over_budget
from ..data.companies import ASHBY_COMPANIES
from ..stats import record_stat
from ..http import SESSION

# ─── ASHBY (REST posting API) ────────────────────────────────────────────────

def scrape_ashby(
    ctx, slug: str, company_name: str
) -> int:
    # I use Ashby's official posting REST API which replaced the __NEXT_DATA__
    # static embed. No API key is required - the endpoint is public.
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    count = 0
    try:
        # I request the JSON endpoint directly rather than scraping the HTML.
        resp = SESSION.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Ashby {company_name}: HTTP {resp.status_code}")
            return 0
        # I iterate the top-level jobs array; the schema is consistent across
        # all employers on this endpoint.
        for job in resp.json().get("jobs", []):
            # I prefer jobUrl but fall back to applyUrl when it is absent.
            title = job.get("title", "")
            location = job.get("location", "")
            job_url = job.get("jobUrl") or job.get("applyUrl", "")
            # Ashby returns the full plain-text description and publish date
            # in the listing response - no extra API call needed.
            description_text = job.get("descriptionPlain", "")
            opening_date = (job.get("publishedAt") or "")[:10] or None
            if is_relevant(title, company_name, location):
                if insert_job(ctx, {
                    "company":               company_name,
                    "role":                  title,
                    "type":                  resolve_type(title),
                    "url":                   job_url,
                    "location":              location,
                    "source":                "Ashby",
                    "opening_date":          opening_date,
                    "sponsors_visa":         detect_sponsors_visa(description_text),
                    "cover_letter_required": detect_cover_letter_required(description_text),
                    "description":          description_text,
                }):
                    count += 1
            elif is_relevant_job(title, company_name, location):
                if insert_job(ctx, {
                    "company":               company_name,
                    "role":                  title,
                    "type":                  "Full-time Job",
                    "url":                   job_url,
                    "location":              location,
                    "source":                "Ashby",
                    "opening_date":          opening_date,
                    "sponsors_visa":         detect_sponsors_visa(description_text),
                    "cover_letter_required": detect_cover_letter_required(description_text),
                    "description":          description_text,
                }):
                    count += 1
        # I sleep 0.6 s between slugs to stay well under Ashby's rate limit.
        time.sleep(0.6)
    except Exception as e:
        print(f"  Error Ashby {company_name}: {e}")
    return count


def run(ctx) -> int:
    print("\n--- Ashby ---")
    total = 0
    for slug, name in ASHBY_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Ashby companies")
            break
        n = scrape_ashby(ctx, slug, name)
        if n:
            print(f"  {name}: {n}")
        total += n
    record_stat(ctx, "Ashby", total)
    return total
