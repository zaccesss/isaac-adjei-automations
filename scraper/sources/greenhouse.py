"""Source: greenhouse."""

import time
import requests
from ..dates import _parse_greenhouse_date
from ..db import insert_job
from ..detect import _strip_html, detect_cover_letter_required, detect_sponsors_visa
from ..filters import infer_type, is_relevant, is_relevant_job
from ..http import HEADERS
from ..budget import over_budget
from ..data.companies import GREENHOUSE_COMPANIES
from ..stats import record_stat

def fetch_greenhouse_location(slug: str, job_id: int) -> str:
    """Call the Greenhouse job detail endpoint to get the office/city name.

    I only call this when the main listing API returned no location. The
    detail endpoint includes an 'offices' array with city-level names.
    """
    url = (
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            offices = resp.json().get("offices") or []
            names = [
                o.get("name", "") for o in offices if o.get("name")
            ]
            if names:
                return ", ".join(names)
    except Exception:
        pass
    return ""


# ─── GREENHOUSE JSON API ────────────────────────────────────────────────────

def scrape_greenhouse(
    ctx, slug: str, company_name: str
) -> int:
    # I use the public Greenhouse boards API which requires no authentication.
    # The ?content=true flag exposes the metadata array I need for location.
    url = (
        f"https://boards-api.greenhouse.io/v1/boards/{slug}"
        f"/jobs?content=true"
    )
    count = 0
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(
                f"  Greenhouse {company_name}: HTTP {resp.status_code}"
            )
            return 0

        for job in resp.json().get("jobs", []):
            title = job.get("title", "")
            job_url = job.get("absolute_url", "")

            # I read the metadata array first because Greenhouse's top-level
            # location field often shows "Multiple Locations" which is useless
            # for UK filtering.
            location = ""
            for meta in job.get("metadata") or []:
                if meta and meta.get("name") == "Job Posting Location":
                    # I check isinstance because the value field can be a list
                    # (e.g. ["London, UK", "Remote"]) for multi-location postings.
                    # Calling .lower() on a list crashes with AttributeError.
                    val = meta.get("value")
                    location = (
                        ", ".join(str(v) for v in val if v)
                        if isinstance(val, list)
                        else (val or "")
                    )
                    break
            # I fall back to the top-level location when metadata lacks a city.
            if not location:
                location = (
                    job.get("location") or {}
                ).get("name", "")
            # I call the detail endpoint when location is still empty because
            # the detail response includes an 'offices' array with city names
            # that the listing endpoint sometimes omits.
            if not location and job.get("id"):
                location = fetch_greenhouse_location(slug, job["id"])
                if location:
                    time.sleep(0.2)

            # I extract department names so is_student_role can check them
            # alongside the title. Some companies like Bloomberg tag their
            # graduate pipeline as a department.
            dept_names = [
                d.get("name", "")
                for d in (job.get("departments") or [])
            ]

            # I extract dates and description from the listing response
            # (content=true already includes these - no extra API call needed).
            description_text = _strip_html(job.get("content", ""))
            opening_date = _parse_greenhouse_date(job.get("first_published"))
            deadline = _parse_greenhouse_date(job.get("application_deadline"))

            if is_relevant(title, company_name, location, dept_names):
                if insert_job(ctx, {
                    "company":              company_name,
                    "role":                 title,
                    "type":                 infer_type(title),
                    "url":                  job_url,
                    "location":             location,
                    "source":               "Greenhouse",
                    "opening_date":         opening_date,
                    "deadline":             deadline,
                    "sponsors_visa":        detect_sponsors_visa(description_text),
                    "cover_letter_required": detect_cover_letter_required(description_text),
                    "description":          description_text,
                }):
                    count += 1
            elif is_relevant_job(title, company_name, location):
                if insert_job(ctx, {
                    "company":              company_name,
                    "role":                 title,
                    "type":                 "Full-time Job",
                    "url":                  job_url,
                    "location":             location,
                    "source":               "Greenhouse",
                    "opening_date":         opening_date,
                    "deadline":             deadline,
                    "sponsors_visa":        detect_sponsors_visa(description_text),
                    "cover_letter_required": detect_cover_letter_required(description_text),
                    "description":          description_text,
                }):
                    count += 1

        # I sleep 0.5 seconds between companies to be a polite scraper.
        time.sleep(0.5)
    except Exception as e:
        print(f"  Error Greenhouse {company_name}: {e}")
    return count


def run(ctx) -> int:
    # I run the JSON API scrapers first because they are the most reliable and
    # fastest - no HTML parsing involved.
    print("\n--- Greenhouse ---")
    total = 0
    for slug, name in GREENHOUSE_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Greenhouse companies")
            break
        n = scrape_greenhouse(ctx, slug, name)
        if n:
            print(f"  {name}: {n}")
        total += n
    record_stat(ctx, "Greenhouse", total)
    return total
