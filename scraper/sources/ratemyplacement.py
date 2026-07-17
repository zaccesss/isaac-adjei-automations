"""Source: RateMyPlacement (embedded JSON).

RateMyPlacement (part of the Higher In platform) is a placements and internships
board that server-renders its results and embeds the whole page of jobs as JSON
in a `window.__RMP_SEARCH_RESULTS_INITIAL_STATE__` assignment. No browser is
needed: I request the search route, read that JSON and page through it.

The board mixes every discipline, so I pull the job types that matter for a
placement year or an internship and filter each page down to genuine tech roles
with the shared classifier. The links point straight at the individual role on
higherin.com, which is exactly the direct per-role link the careers-page-only
Trackr rows lack - this is a source of specific apply links, not landing pages.
"""
import json
import re
import time

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword
from ..http import HEADERS, SESSION
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.ratemyplacement.co.uk/search-jobs"

# The embedded state is a single JSON object assigned before the closing script
# tag; I capture up to that tag so a later inline script cannot swallow it.
_STATE_RE = re.compile(
    r"window\.__RMP_SEARCH_RESULTS_INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>",
    re.S,
)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# Early in the cycle the board is mostly "Register Your Interest - <role>"
# pre-registration listings. Those are worth keeping (registering early is the
# right move for a placement year), but the prefix clutters the stored title and
# blunts the tech filter, so I strip it and classify on the real role underneath.
_PREREG_PREFIX_RE = re.compile(r"^register your interest\s*[-–—:]\s*", re.I)

# Only these job-type slugs actually filter the server-rendered feed (verified
# July 2026); the graduate slugs are ignored by the site and return the whole
# board, so I leave graduate schemes to the Trackr, which already covers them.
# Each maps to the type the app files it under.
TYPE_SLUGS = {
    "placement":               "Industrial Placement",
    "internship":              "Internship",
    "insight-vacation-scheme": "Spring Week",
}


def _first_location(names: str) -> str:
    """Return the first city from RateMyPlacement's comma-joined location list."""
    if not names:
        return ""
    return names.split(",")[0].strip()


def _clean_deadline(value) -> "str | None":
    """Return an ISO date deadline, or None - the feed often has no deadline."""
    if isinstance(value, str) and _ISO_DATE_RE.match(value):
        return value[:10]
    return None


def fetch_page(job_type: str, page: int) -> "tuple[list, int]":
    """Return (jobs, last_page) for one job-type page, or ([], 1) on failure."""
    try:
        resp = SESSION.get(
            BASE,
            params={"type": job_type, "page": page},
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"  RateMyPlacement {job_type} p{page}: HTTP {resp.status_code}")
            return [], 1
        m = _STATE_RE.search(resp.text)
        if not m:
            return [], 1
        data = json.loads(m.group(1))
        jobs = data.get("data") or []
        last = (
            (data.get("meta") or {}).get("pagination", {}).get("lastPage", 1)
        )
        return jobs, int(last or 1)
    except Exception as e:
        print(f"  Error RateMyPlacement {job_type} p{page}: {e}")
        return [], 1


def scrape_ratemyplacement(ctx) -> int:
    """Pull every tech placement, internship and vacation scheme on the board."""
    print("\nScraping RateMyPlacement...")
    total = 0
    for slug, job_type in TYPE_SLUGS.items():
        count = 0
        first_jobs, last_page = fetch_page(slug, 1)
        # I cap the page walk at the reported last page so a change in the
        # response can never spin this into an unbounded loop.
        for page in range(1, min(last_page, 40) + 1):
            jobs = first_jobs if page == 1 else fetch_page(slug, page)[0]
            if not jobs:
                break
            for job in jobs:
                role = _PREREG_PREFIX_RE.sub("", (job.get("jobTitle") or "").strip()).strip()
                company = (job.get("companyName") or "").strip()
                if not role or not company:
                    continue
                # The board carries every discipline, so I keep only genuine
                # tech roles: a tech keyword must be present, senior and clearly
                # non-tech titles are dropped. The job type already establishes
                # that these are student placements, so I do not require an
                # intern word in the title the way the ATS sources do.
                if _SENIOR_ROLE_RE.search(role):
                    continue
                if not _has_tech_keyword(role.lower()):
                    continue
                if _NON_TECH_ROLE_RE.search(role):
                    continue
                if insert_job(ctx, {
                    "company":      company,
                    "role":         role,
                    "type":         job_type,
                    "url":          (job.get("url") or "").strip(),
                    "location":     normalize_location(
                        _first_location(job.get("jobLocationNames", ""))
                    ),
                    "deadline":     _clean_deadline(job.get("deadline")),
                    "salary_range": (job.get("salary") or "").strip(),
                    "source":       "RateMyPlacement",
                }):
                    count += 1
            time.sleep(0.5)
        if count:
            print(f"  {slug}: {count} new")
        total += count
    print(f"  RateMyPlacement total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- RateMyPlacement ---")
    try:
        n = scrape_ratemyplacement(ctx)
        record_stat(ctx, "RateMyPlacement", n)
        return n
    except Exception as e:
        print(f"  Error RateMyPlacement: {e}")
        record_stat(ctx, "RateMyPlacement", 0, str(e))
        return 0
