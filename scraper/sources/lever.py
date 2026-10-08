"""Source: lever."""

import time
from ..db import insert_job
from ..filters import resolve_type, is_relevant, is_relevant_job
from ..http import HEADERS
from ..budget import over_budget
from ..data.companies import LEVER_COMPANIES
from ..stats import record_stat
from ..http import SESSION


def _lever_date(ms):
    """Lever's createdAt is milliseconds since the epoch; the table wants a plain date."""
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None

def fetch_lever_details(slug: str, posting_id: str) -> dict:
    """Call the Lever individual posting endpoint for extra fields.

    Lever's list API sometimes omits location at the top level. The single
    posting endpoint returns the same structure but can have additional
    fields populated - I extract location and any workplaceType hint.
    """
    url = f"https://api.lever.co/v0/postings/{slug}/{posting_id}"
    try:
        resp = SESSION.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            resp = SESSION.get(url.replace("api.lever.co", "api.eu.lever.co"), headers=HEADERS, timeout=10)
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
    ctx, slug: str, company_name: str
) -> int:
    # use Lever's v0 public postings endpoint which returns all jobs as a
    # flat JSON array. mode=json returns structured data not an HTML page.
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    # European employers (Cirrus Logic, Quantinuum) live on Lever's EU host, which the US host
    # answers with 404
    probe = SESSION.get(url, headers=HEADERS, timeout=15)
    if probe.status_code == 404:
        url = f"https://api.eu.lever.co/v0/postings/{slug}?mode=json"
    count = 0
    try:
        resp = SESSION.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Lever {company_name}: HTTP {resp.status_code}")
            return 0

        for job in resp.json():
            # use "text" because Lever calls it that rather than "title".
            title = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            work_mode = job.get("workplaceType", "")
            # prefer hostedUrl over applyUrl because it shows the full JD.
            job_url = job.get("hostedUrl", "")
            posting_id = job.get("id", "")
            # call the detail endpoint when location is empty because
            # Lever's listing API sometimes omits the location field.
            if not location and posting_id:
                extra = fetch_lever_details(slug, posting_id)
                location = extra.get("location", "")
                work_mode = work_mode or extra.get("work_mode", "")
                if location:
                    time.sleep(0.2)

            if is_relevant(title, company_name, location):
                if insert_job(ctx, {
                    "company":   company_name,
                    "role":      title,
                    "type":      resolve_type(title),
                    "url":       job_url,
                    "location":  location,
                    "work_mode": work_mode,
                    "source":    "Lever",
                    "description": job.get("descriptionPlain", ""),
                    "opening_date": _lever_date(job.get("createdAt")),
                    "salary_min": (job.get("salaryRange") or {}).get("min"),
                    "salary_max": (job.get("salaryRange") or {}).get("max"),
                }):
                    count += 1
            elif is_relevant_job(title, company_name, location):
                if insert_job(ctx, {
                    "company":   company_name,
                    "role":      title,
                    "type":      "Full-time Job",
                    "url":       job_url,
                    "location":  location,
                    "work_mode": work_mode,
                    "source":    "Lever",
                }):
                    count += 1

        time.sleep(0.5)
    except Exception as e:
        print(f"  Error Lever {company_name}: {e}")
    return count


def run(ctx) -> int:
    print("\n--- Lever ---")
    total = 0
    for slug, name in LEVER_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Lever companies")
            break
        n = scrape_lever(ctx, slug, name)
        if n:
            print(f"  {name}: {n}")
        total += n
    record_stat(ctx, "Lever", total)
    return total
