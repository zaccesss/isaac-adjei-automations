"""Source: trackr."""

import time
from ..data.keywords import TECH_KEYWORDS
from ..dates import _parse_trackr_date
from ..db import insert_job
from ..filters import _SENIOR_ROLE_RE, is_relevant
from ..stats import record_stat

# ─── THE TRACKR (Playwright - JS rendered) ──────────────────────────────────


def _trackr_col(cells, colmap: "dict[str, int]", key: str) -> str:
    """Return the trimmed text of the mapped column for this row, or ''."""
    idx = colmap.get(key)
    if idx is None or idx >= len(cells):
        return ""
    return (cells[idx].inner_text() or "").strip()


def scrape_trackr_all(ctx) -> int:
    """Scrape all four Trackr categories using a headless browser.

    I use Playwright rather than requests here because The Trackr is a React
    SPA - the job table is injected into the DOM by JavaScript after the
    initial page load, so a plain HTTP GET returns an empty shell.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    # I map each URL slug to the type label I want to store in the DB.
    categories = [
        ("summer-internships",    "Internship"),
        ("industrial-placements", "Industrial Placement"),
        ("graduate-schemes",      "Graduate"),
        ("spring-weeks",          "Spring Week"),
    ]

    total = 0
    print("\nScraping The Trackr (headless)...")

    with sync_playwright() as p:
        # I use a single browser instance across all four pages to share
        # startup overhead.
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={"Accept-Language": "en-GB,en;q=0.9"},
        )
        # Hide navigator.webdriver so bot-detection scripts see a real browser.
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for slug, job_type in categories:
            url = f"https://app.the-trackr.com/uk-technology/{slug}"
            print(f"  -> {url}")
            # I open a fresh page per category rather than navigating in-place
            # to avoid leftover React state polluting the next render.
            page = context.new_page()
            count = 0

            try:
                # I wait for "networkidle" so the React data-fetching hooks
                # have had time to run and the table is populated.
                page.goto(url, wait_until="networkidle", timeout=30000)

                # I use a secondary wait for table rows because networkidle
                # can fire before the final render cycle if the data fetch
                # completes just after the last network request.
                try:
                    page.wait_for_selector(
                        "table tbody tr, [role='row']",
                        timeout=15000,
                    )
                except PWTimeout:
                    print(f"     Timed out waiting for rows on {slug}")
                    page.close()
                    continue

                rows = page.query_selector_all(
                    "table tbody tr, [role='row']"
                )
                print(f"     Found {len(rows)} rows")

                # I map the column headers to indices once per page so each
                # field is read from the correct column. Header wording varies,
                # so I match on keywords; unmatched fields fall back to the date
                # scan further down.
                colmap: "dict[str, int]" = {}
                for _i, _h in enumerate(page.query_selector_all(
                    "table thead th, table thead td, [role='columnheader']"
                )):
                    _label = (_h.inner_text() or "").strip().lower()
                    if "location" in _label:
                        colmap.setdefault("location", _i)
                    elif "last year" in _label or "last-year" in _label:
                        colmap.setdefault("last_year", _i)
                    elif "open" in _label:
                        colmap.setdefault("opening", _i)
                    elif "clos" in _label or "deadline" in _label:
                        colmap.setdefault("closing", _i)
                    elif _label == "cv":
                        colmap.setdefault("cv", _i)
                    elif "cover" in _label:
                        colmap.setdefault("cover", _i)
                    elif "written" in _label:
                        colmap.setdefault("written", _i)
                    elif "sponsor" in _label:
                        colmap.setdefault("sponsors", _i)

                for row in rows:
                    cells = row.query_selector_all("td, [role='cell']")
                    # I skip rows with fewer than 2 cells because they are
                    # likely header or spacer rows.
                    if len(cells) < 2:
                        continue

                    # I prefer a link with "company" in its href because it
                    # reliably points to the company page rather than a
                    # programme detail page.
                    company_el = (
                        row.query_selector("a[href*='company']")
                        or row.query_selector(
                            "a[href*='/uk-technology/']"
                        )
                        # I fall back to the first cell as a last resort.
                        or (cells[0] if cells else None)
                    )
                    # I use the second link as the programme link because the
                    # first is always the company.
                    all_links = row.query_selector_all("a")
                    prog_el = (
                        all_links[1]
                        if len(all_links) > 1
                        else (cells[1] if len(cells) > 1 else None)
                    )

                    company = (
                        company_el.inner_text().strip()
                        if company_el else ""
                    )
                    programme = (
                        prog_el.inner_text().strip()
                        if prog_el else ""
                    )
                    # I capture the application link, preferring an external
                    # "apply" link over a the-trackr.com internal page so the
                    # app opens the real posting.
                    job_url = ""
                    for _a in all_links:
                        _href = _a.get_attribute("href") or ""
                        if _href.startswith("http") and "the-trackr.com" not in _href:
                            job_url = _href
                            break
                    if not job_url and prog_el:
                        job_url = prog_el.get_attribute("href") or ""
                    # I prepend the origin when the href is relative so the
                    # stored URL is always absolute.
                    if job_url and not job_url.startswith("http"):
                        job_url = (
                            f"https://app.the-trackr.com{job_url}"
                        )

                    # I read the date and location columns by name. Where a
                    # header was not matched I fall back to scanning the
                    # trailing cells for the first two parseable dates (opening
                    # then closing), preserving the old behaviour.
                    opening_date = _parse_trackr_date(
                        _trackr_col(cells, colmap, "opening")
                    )
                    closing_date = _parse_trackr_date(
                        _trackr_col(cells, colmap, "closing")
                    )
                    last_year_opening = _parse_trackr_date(
                        _trackr_col(cells, colmap, "last_year")
                    )
                    if opening_date is None and closing_date is None:
                        _seen_dates = []
                        for cell in cells[2:]:
                            _d = _parse_trackr_date(
                                (cell.inner_text() or "").strip()
                            )
                            if _d:
                                _seen_dates.append(_d)
                            if len(_seen_dates) == 2:
                                break
                        if _seen_dates:
                            opening_date = _seen_dates[0]
                            if len(_seen_dates) > 1:
                                closing_date = _seen_dates[1]
                    location = _trackr_col(cells, colmap, "location")
                    # The Trackr lists the real per-role CV / cover letter /
                    # written-answers / visa-sponsorship values, so I read them
                    # rather than hardcoding "Yes" for every row.
                    cv_req = _trackr_col(cells, colmap, "cv")
                    cover_req = _trackr_col(cells, colmap, "cover")
                    written = _trackr_col(cells, colmap, "written")
                    sponsors = _trackr_col(cells, colmap, "sponsors")

                    # I silently skip rows where company or programme could
                    # not be parsed.
                    if not company or not programme:
                        continue
                    # I bypass the student-term check for placement and
                    # spring-week categories because the category URL already
                    # tells me the role type - requiring "placement" in every
                    # title would drop most real results.
                    if job_type == "Internship":
                        if not is_relevant(programme, company):
                            continue
                    else:
                        # I still require a tech keyword for non-internship
                        # categories so non-tech roles are skipped.
                        if not any(
                            k in programme.lower() for k in TECH_KEYWORDS
                        ):
                            continue
                        # I also reject senior titles even from placement and
                        # grad-scheme categories - The Trackr occasionally
                        # lists staff or lead roles under these buckets.
                        if _SENIOR_ROLE_RE.search(programme):
                            continue

                    if insert_job(ctx, {
                        "company":           company,
                        "role":              programme,
                        "type":              job_type,
                        "url":               job_url or "",
                        "source":            "The Trackr",
                        "deadline":          closing_date,
                        "opening_date":      opening_date,
                        "location":          location,
                        "last_year_opening": last_year_opening,
                        # I reuse the job's city for the housing search link so
                        # the app's "Find Housing" column is populated.
                        "housing_location":  location,
                        "cv_required":            cv_req or None,
                        "cover_letter_required":  cover_req or None,
                        "written_answers":        written or None,
                        "sponsors_visa":          sponsors or None,
                    }):
                        count += 1

            except Exception as e:
                print(f"     Error on {slug}: {e}")
            finally:
                # I always close the page in the finally block so the browser
                # does not accumulate open tabs on error.
                page.close()

            print(f"     Added {count} from {slug}")
            total += count
            # I sleep 2 seconds between categories to avoid rate limiting.
            time.sleep(2)

        browser.close()

    return total


def run(ctx) -> int:
    # I guard the call site too because an uncaught exception here would abort the
    # whole run - the try/except inside scrape_trackr_all only catches per-category
    # errors, not startup failures.
    try:
        n = scrape_trackr_all(ctx)
        record_stat(ctx, "The Trackr", n)
        return n
    except Exception as e:
        print(f"  Error The Trackr: {e}")
        record_stat(ctx, "The Trackr", 0, str(e))
        return 0
