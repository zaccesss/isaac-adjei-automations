"""Source: The Trackr (JSON API).

The Trackr is an Angular SPA backed by api.the-trackr.com. The old scraper drove
a headless browser and read the rendered table, so a programme whose apply link
sat one hop away - on the company page, reached by clicking the company name
rather than the row - came through link-less. That was the whole FAANG
missing-links problem: the real posting URL was never in the row the browser read.

The public programmes endpoint returns every field the table shows as clean
JSON, including the direct apply `url` and, where that is blank, the company
`careersSite`. Both are real external destinations, never a the-trackr.com page,
so I query the API directly. No browser, no missing links, and the per-role CV /
cover-letter / written-answer / visa flags and the opening and closing dates all
arrive structured instead of being scraped out of table cells.

I discovered the contract from the Angular bundle and the API's own 422 body:
GET /programmes?region=UK&industry=Tech&season=2026&type=summer-internships
with an app.the-trackr.com Origin. region, industry and season are validated
enums; type is the tab slug. I pull every tab and both live cycles.
"""
import time
from datetime import datetime, timezone

from ..db import insert_job
from ..filters import _SENIOR_ROLE_RE
from ..http import HEADERS, SESSION
from ..stats import record_stat

API = "https://api.the-trackr.com/programmes"

# The Trackr splits UK Tech into these tabs; each tab is a `type` value on the
# API. I request every one so nothing is missed - Summer Internships, Industrial
# Placements, Graduate Schemes, Spring Weeks, Pre-Uni and Events. A tab with no
# entries for a season simply returns an empty list, so listing the two that are
# empty this cycle (insight-programmes, pre-uni) costs nothing and future-proofs
# the source for when the Trackr populates them.
TYPE_TO_CATEGORY = {
    "summer-internships":    "Internship",
    "industrial-placements": "Industrial Placement",
    "graduate-programmes":   "Graduate",
    "spring-weeks":          "Spring Week",
    "insight-programmes":    "Event",
    "events":                "Event",
    "pre-uni":               "Event",
}

# The endpoint rejects calls without the app Origin, so I always send it. The
# API scopes the whole feed to UK Tech already, so I do not re-filter by location
# or tech keyword - the tab decides the category.
_API_HEADERS = {
    **HEADERS,
    "Accept": "application/json",
    "Origin": "https://app.the-trackr.com",
    "Referer": "https://app.the-trackr.com/",
}


def _iso_date(value) -> "str | None":
    """Return the YYYY-MM-DD slice of an ISO timestamp, or None."""
    if isinstance(value, str) and len(value) >= 10 and value[4] == "-":
        return value[:10]
    return None


def _yes_no(value) -> "str | None":
    """Normalise the API's mixed booleans and labels to the app's text values.

    cv arrives as a real bool; coverLetter and writtenAnswers arrive as
    "Yes"/"No"/"Optional" strings; sponsorsVisa is a bool. The app stores all of
    them as text labels, so I map booleans and pass existing labels through.
    """
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _locations(value) -> str:
    """Join the locations array whether it holds strings or {name/city} dicts."""
    if not isinstance(value, list):
        return ""
    parts = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            parts.append(item.get("name") or item.get("city") or "")
    return ", ".join(p for p in parts if p)


def _seasons() -> "list[str]":
    """The current recruiting cycle and the next one.

    The Trackr labels a cycle by its intake year and keeps two live at once
    (verified July 2026: 2026 and 2027 both return data). Pulling the current
    year and the year after tracks the roll-over without a code change, and the
    owner - a second year hunting a 2027 year-long placement - needs the later
    cycle as much as the current one.
    """
    year = datetime.now(timezone.utc).year
    return [str(year), str(year + 1)]


def fetch_programmes(season: str, type_slug: str) -> list:
    """GET one tab of one cycle as JSON, or [] on any non-200 or error."""
    try:
        resp = SESSION.get(
            API,
            params={
                "region": "UK",
                "industry": "Tech",
                "season": season,
                "type": type_slug,
            },
            headers=_API_HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"  Trackr {type_slug} {season}: HTTP {resp.status_code}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  Error Trackr {type_slug} {season}: {e}")
        return []


def scrape_trackr_all(ctx) -> int:
    """Pull every UK Tech tab across the live cycles straight from the API."""
    print("\nScraping The Trackr (JSON API)...")
    total = 0
    for season in _seasons():
        for type_slug, category in TYPE_TO_CATEGORY.items():
            programmes = fetch_programmes(season, type_slug)
            if not programmes:
                continue
            count = 0
            for prog in programmes:
                company_obj = prog.get("company") or {}
                company = (company_obj.get("name") or "").strip()
                role = (prog.get("name") or "").strip()
                if not company or not role:
                    continue
                # Senior or lead titles are never a student programme even when
                # the Trackr files one under an early-careers tab, so I drop them
                # rather than store a role the owner cannot apply to.
                if _SENIOR_ROLE_RE.search(role):
                    continue

                # The direct apply link first; the company careers site when the
                # Trackr has no per-programme link yet. Both are real external
                # pages - this is the fix for the company-name-only links.
                url = (
                    prog.get("url") or company_obj.get("careersSite") or ""
                ).strip()

                if insert_job(ctx, {
                    "company":                company,
                    "role":                   role,
                    "type":                   category,
                    "url":                    url,
                    "source":                 "The Trackr",
                    "location":               _locations(prog.get("locations")),
                    "housing_location":       company_obj.get("ukHousingLocation") or "",
                    "opening_date":           _iso_date(prog.get("openingDate")),
                    "deadline":               _iso_date(prog.get("closingDate")),
                    "last_year_opening":      _iso_date(prog.get("lastYearOpening")),
                    "cv_required":            _yes_no(prog.get("cv")),
                    "cover_letter_required":  _yes_no(prog.get("coverLetter")),
                    "written_answers":        _yes_no(prog.get("writtenAnswers")),
                    "sponsors_visa":          _yes_no(company_obj.get("sponsorsVisa")),
                }):
                    count += 1
            if count:
                print(f"  {type_slug} {season}: {count} new")
            total += count
            # The endpoint rate-limits a rapid burst (429 after ~6 fast calls),
            # so I space the tab requests out.
            time.sleep(2)
    print(f"  The Trackr total: {total} new")
    return total


def run(ctx) -> int:
    # I guard the call site because an uncaught error here would abort the whole
    # run - fetch_programmes already swallows per-request failures, but a bad
    # season loop or a JSON change should degrade to zero, not crash the scraper.
    try:
        n = scrape_trackr_all(ctx)
        record_stat(ctx, "The Trackr", n)
        return n
    except Exception as e:
        print(f"  Error The Trackr: {e}")
        record_stat(ctx, "The Trackr", 0, str(e))
        return 0
