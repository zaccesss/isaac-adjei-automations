"""Source: company sites."""
from ..db import dedupe_key, insert_job
from ..filters import infer_type, is_relevant
from ..locations import normalize_location
from ..stats import _record_stat


# ─── COMPANY CAREER SITES (Playwright - proprietary ATSes) ──────────────────
# Google, Meta, ARM, Goldman Sachs and JPMorgan do not expose a public REST API.
# ARM and JPMorgan use Workday but require session cookies the CXS API rejects.
# I open one shared browser for all five companies to reduce startup overhead.

def scrape_company_sites_playwright(existing_keys: set) -> int:
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
                    if key in existing_keys:
                        continue
                    insert_job({
                        "company": "Google",
                        "role": title,
                        "location": normalize_location(location),
                        "url": url,
                        "type": infer_type(title),
                        "cv_required": True,
                    }, existing_keys)
                    existing_keys.add(key)
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
        _record_stat("Google Careers", count)

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
                if key in existing_keys:
                    continue
                insert_job({
                    "company": "Meta",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                }, existing_keys)
                existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     Meta error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     Meta: {count} new")
        total += count
        _record_stat("Meta Careers", count)

        # ── ARM Careers ─────────────────────────────────────────────────────
        # ARM uses Workday (arm.wd1.myworkdayjobs.com) but the CXS REST API
        # returns 422 - session auth is required. Playwright renders the page.
        page = context.new_page()
        count = 0
        try:
            print("  -> ARM Careers")
            page.goto(
                "https://careers.arm.com/search"
                "#q=intern&t=Jobs&numberOfResults=25"
                "&f:@sfdclocations=[United%20Kingdom]",
                wait_until="networkidle",
                timeout=30000,
            )
            try:
                page.wait_for_selector(
                    "a[href*='arm.wd1'], .CoveoResult a,"
                    " [class*='JobItem'], a[class*='result']",
                    timeout=15000,
                )
            except PWTimeout:
                print("     ARM: timed out")
                page.close()
                page = context.new_page()
                raise RuntimeError("timeout")

            links = page.query_selector_all(
                "a[href*='arm.wd1'], .CoveoResultLink, [class*='result-link']"
            )
            for link in links:
                title = link.inner_text().strip()
                if not title:
                    continue
                href = link.get_attribute("href") or ""
                url = (href if href.startswith("http")
                       else f"https://careers.arm.com{href}")

                parent = link.evaluate_handle(
                    "el => el.closest('li, .CoveoResult, [class*=Result]')"
                )
                if parent.as_element():
                    loc_el = parent.as_element().query_selector(
                        "[class*='location'], [field='@sfdclocations']"
                    )
                    location = (loc_el.inner_text().strip()
                                if loc_el else "United Kingdom")
                else:
                    location = "United Kingdom"

                if not is_relevant(title, "ARM", location):
                    continue
                key = dedupe_key("ARM", title, url)
                if key in existing_keys:
                    continue
                insert_job({
                    "company": "ARM",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                }, existing_keys)
                existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     ARM error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     ARM: {count} new")
        total += count
        _record_stat("ARM Careers", count)

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
                if key in existing_keys:
                    continue
                insert_job({
                    "company": "Goldman Sachs",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                }, existing_keys)
                existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     Goldman error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     Goldman Sachs: {count} new")
        total += count
        _record_stat("Goldman Sachs", count)

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
                if key in existing_keys:
                    continue
                insert_job({
                    "company": "JPMorgan",
                    "role": title,
                    "location": normalize_location(location),
                    "url": url,
                    "type": infer_type(title),
                    "cv_required": True,
                }, existing_keys)
                existing_keys.add(key)
                count += 1

        except Exception as exc:
            print(f"     JPMorgan error: {exc}")
        finally:
            page.close()

        if count:
            print(f"     JPMorgan: {count} new")
        total += count
        _record_stat("JPMorgan Careers", count)

        browser.close()

    print(f"  Company sites total: {total} new")
    return total
