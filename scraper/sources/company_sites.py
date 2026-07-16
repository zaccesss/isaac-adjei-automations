"""Source: company sites."""
import re

from bs4 import BeautifulSoup

from ..http import HEADERS, SESSION

from ..db import dedupe_key, insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from ..stats import record_stat


# ─── COMPANY CAREER SITES (Playwright - proprietary ATSes) ──────────────────
# Google, Meta, ARM, Goldman Sachs and JPMorgan do not expose a public REST API.
# ARM and JPMorgan use Workday but require session cookies the CXS API rejects.
# I open one shared browser for all five companies to reduce startup overhead.

def scrape_company_sites_playwright(ctx) -> int:
    """Scrape Google, Meta, ARM, Goldman Sachs and JPMorgan via headless browser.

    Each company gets its own page inside a single Chromium session. I use
    broad selector fallbacks (h2|h3|a, etc.) because these React SPAs update
    their class names on every build. URL dedup at the DB level means running
    more than once is always safe.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    total = 0
    print("\nScraping company career sites (headless)...")

    with sync_playwright() as p:
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
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # ── Google Careers ──────────────────────────────────────────────────
        page = context.new_page()
        count = 0
        try:
            print("  -> Google Careers")
            page.goto(
                "https://careers.google.com/jobs/results/"
                "?q=intern&location=United+Kingdom&employment_type=INTERN",
                wait_until="networkidle",
                timeout=30000,
            )
            try:
                page.wait_for_selector(
                    "[data-job-id], li[jsname], .lLd3Je",
                    timeout=15000,
                )
            except PWTimeout:
                print("     Google: timed out waiting for job cards")
                page.close()
                page = context.new_page()
                raise RuntimeError("timeout")

            while True:
                cards = page.query_selector_all(
                    "[data-job-id], li[jsname]"
                )
                for card in cards:
                    title_el = (card.query_selector("h3")
                                or card.query_selector("[jsname='N8A5Hb']"))
                    if not title_el:
                        continue
                    title = title_el.inner_text().strip()

                    loc_el = (card.query_selector(".KF4T6b")
                              or card.query_selector("[jsname='MkUkrc']")
                              or card.query_selector(".lLd3Je span"))
                    location = loc_el.inner_text().strip() if loc_el else "United Kingdom"

                    link_el = card.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""
                    url = (f"https://careers.google.com{href}"
                           if href and href.startswith("/") else href or "")

                    if not is_relevant(title, "Google", location):
                        continue
                    key = dedupe_key("Google", title, url)
                    if key in ctx.existing_keys:
                        continue
                    insert_job(ctx, {
                        "company": "Google",
                        "role": title,
                        "location": normalize_location(location),
                        "url": url,
                        "type": infer_type(title),
                        "cv_required": True,
                    })
                    ctx.existing_keys.add(key)
                    count += 1

                next_btn = (page.query_selector("a[aria-label='Next page']")
                            or page.query_selector("[jsaction*='nextPage']"))
                if not next_btn:
                    break
                next_btn.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PWTimeout:
                    break

        except Exception as exc:
            print(f"     Google error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     Google: {count} new")
        total += count
        record_stat(ctx, "Google Careers", count)

        # ── Meta Careers ────────────────────────────────────────────────────
        page = context.new_page()
        count = 0
        try:
            print("  -> Meta Careers")
            page.goto(
                "https://www.metacareers.com/jobs"
                "?offices%5B0%5D=London%2C%20England&q=intern",
                wait_until="networkidle",
                timeout=30000,
            )
            try:
                page.wait_for_selector(
                    "a[data-testid='job-list-item-link'],"
                    " ._9ata, [class*='jobCard'], article",
                    timeout=15000,
                )
            except PWTimeout:
                print("     Meta: timed out")
                page.close()
                page = context.new_page()
                raise RuntimeError("timeout")

            cards = page.query_selector_all(
                "a[data-testid='job-list-item-link'], ._9ata,"
                " [class*='jobCard'], [class*='job-item']"
            )
            for card in cards:
                title_el = (card.query_selector(
                    "[data-testid='job-title'], h2, h3"
                ) or card.query_selector("span.x193iq5w"))
                if not title_el:
                    continue
                title = title_el.inner_text().strip()

                loc_el = card.query_selector(
                    "[data-testid='job-location'], [class*='location']"
                )
                location = loc_el.inner_text().strip() if loc_el else "London, UK"

                href = card.get_attribute("href") or ""
                url = (f"https://www.metacareers.com{href}"
                       if href and not href.startswith("http") else href)

                if not is_relevant(title, "Meta", location):
                    continue
                key = dedupe_key("Meta", title, url)
                if key in ctx.existing_keys:
                    continue
                insert_job(ctx, {
                    "company": "Meta",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                })
                ctx.existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     Meta error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     Meta: {count} new")
        total += count
        record_stat(ctx, "Meta Careers", count)

        # ── ARM Careers ─────────────────────────────────────────────────────
        # ARM's old Coveo search page is gone (it 404s now). Their Radancy careers
        # site answers plain JSON without a browser: the results endpoint returns
        # rendered rows in a "results" field, the city sits in the /job/{city}/...
        # path and the titles come from the anchors. No Playwright needed.
        count = 0
        try:
            print("  -> ARM Careers")
            seen_hrefs = set()
            for page_no in range(1, 7):
                resp = SESSION.get(
                    "https://careers.arm.com/search-jobs/results",
                    params={
                        "ActiveFacetID": 0,
                        "CurrentPage": page_no,
                        "RecordsPerPage": 50,
                        "SearchResultsModuleName": "Search Results",
                        "SearchFiltersModuleName": "Search Filters",
                        "SearchType": 5,
                    },
                    headers={**HEADERS, "Accept": "application/json"},
                    timeout=20,
                )
                if resp.status_code != 200:
                    break
                payload = resp.json()
                soup = BeautifulSoup(payload.get("results", ""), "html.parser")
                anchors = soup.select("a[href^='/job/']")
                if not payload.get("hasJobs") or not anchors:
                    break
                for a in anchors:
                    href = a.get("href") or ""
                    m = re.match(r"^/job/([^/]+)/", href)
                    if not m or href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)
                    title = " ".join(a.get_text(" ", strip=True).split())
                    if not title:
                        continue
                    city = m.group(1).replace("-", " ").title()
                    url = f"https://careers.arm.com{href}"
                    if not is_relevant(title, "ARM", city):
                        continue
                    key = dedupe_key("ARM", title, url)
                    if key in ctx.existing_keys:
                        continue
                    insert_job(ctx, {
                        "company": "ARM",
                        "role": title,
                        "location": normalize_location(city),
                        "url": url,
                        "type": infer_type(title),
                        "cv_required": True,
                    })
                    ctx.existing_keys.add(key)
                    count += 1
                if len(anchors) < 5:
                    break
        except Exception as exc:
            print(f"     ARM error: {exc}")

        if count:
            print(f"     ARM: {count} new")
        total += count
        record_stat(ctx, "ARM Careers", count)

        # ── Goldman Sachs ───────────────────────────────────────────────────
        page = context.new_page()
        count = 0
        try:
            print("  -> Goldman Sachs Careers")
            page.goto(
                "https://higher.gs.com/roles?region=EMEA&term=intern",
                wait_until="networkidle",
                timeout=30000,
            )
            try:
                page.wait_for_selector(
                    "[class*='RoleCard'], [class*='role-card'],"
                    " article, li[class*='card']",
                    timeout=15000,
                )
            except PWTimeout:
                print("     Goldman: timed out")
                page.close()
                page = context.new_page()
                raise RuntimeError("timeout")

            cards = page.query_selector_all(
                "[class*='RoleCard'], [class*='role-card'],"
                " article, li[class*='card']"
            )
            for card in cards:
                title_el = card.query_selector("h2, h3, [class*='title']")
                if not title_el:
                    continue
                title = title_el.inner_text().strip()

                loc_el = card.query_selector("[class*='location']")
                location = loc_el.inner_text().strip() if loc_el else ""

                link_el = card.query_selector("a[href]")
                href = link_el.get_attribute("href") if link_el else ""
                url = (f"https://higher.gs.com{href}"
                       if href and href.startswith("/") else href or "")

                if not is_relevant(title, "Goldman Sachs", location):
                    continue
                key = dedupe_key("Goldman Sachs", title, url)
                if key in ctx.existing_keys:
                    continue
                insert_job(ctx, {
                    "company": "Goldman Sachs",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                })
                ctx.existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     Goldman error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     Goldman Sachs: {count} new")
        total += count
        record_stat(ctx, "Goldman Sachs", count)

        # ── JPMorgan Careers ────────────────────────────────────────────────
        page = context.new_page()
        count = 0
        try:
            print("  -> JPMorgan Careers")
            page.goto(
                "https://careers.jpmorgan.com/search"
                "?keyword=intern&location=United+Kingdom",
                wait_until="networkidle",
                timeout=30000,
            )
            try:
                page.wait_for_selector(
                    "[data-testid='job-row'], .job-row,"
                    " [class*='JobSearchCard'], article",
                    timeout=15000,
                )
            except PWTimeout:
                print("     JPMorgan: timed out")
                page.close()
                page = context.new_page()
                raise RuntimeError("timeout")

            cards = page.query_selector_all(
                "[data-testid='job-row'], .job-row,"
                " [class*='JobSearchCard'], [class*='job-card']"
            )
            for card in cards:
                title_el = card.query_selector(
                    "a, h2, h3, [class*='title'], [data-testid='job-title']"
                )
                if not title_el:
                    continue
                title = title_el.inner_text().strip()

                loc_el = card.query_selector(
                    "[class*='location'], [data-testid='location']"
                )
                location = loc_el.inner_text().strip() if loc_el else ""

                link_el = card.query_selector("a[href]")
                href = link_el.get_attribute("href") if link_el else ""
                url = (f"https://careers.jpmorgan.com{href}"
                       if href and href.startswith("/") else href or "")

                if not is_relevant(title, "JPMorgan", location):
                    continue
                key = dedupe_key("JPMorgan", title, url)
                if key in ctx.existing_keys:
                    continue
                insert_job(ctx, {
                    "company": "JPMorgan",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                })
                ctx.existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     JPMorgan error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     JPMorgan: {count} new")
        total += count
        record_stat(ctx, "JPMorgan Careers", count)

        browser.close()

    print(f"  Company sites total: {total} new")
    return total


def run(ctx) -> int:
    try:
        return scrape_company_sites_playwright(ctx)
    except Exception as e:
        print(f"  Error company career sites: {e}")
        return 0
