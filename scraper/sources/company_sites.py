"""Source: company sites."""
import re

from bs4 import BeautifulSoup

from ..http import HEADERS, SESSION

from ..db import dedupe_key, insert_job
from ..filters import resolve_type, is_relevant
from ..locations import normalize_location
from ..stats import record_stat


# ─── COMPANY CAREER SITES (Playwright - proprietary ATSes) ──────────────────
# Google, Meta, ARM, Goldman Sachs and JPMorgan do not expose a public REST API.
# ARM and JPMorgan use Workday but require session cookies the CXS API rejects.
# open one shared browser for all five companies to reduce startup overhead.

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
                        "type": resolve_type(title),
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
                    "type": resolve_type(title),
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
        # read from the careers site's sitemap since November 2026: robots.txt
        # disallows /search-jobs/, which the old results endpoint sat under.
        count = 0
        try:
            print("  -> ARM Careers")
            count = scrape_arm_sitemap(ctx)
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
                    "type": resolve_type(title),
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
                    "type": resolve_type(title),
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


# ─── ARM SITEMAP ────────────────────────────────────────────────────────────

ARM_SITEMAP = "https://careers.arm.com/sitemap.xml"
_ARM_JOB_RE = re.compile(r"^https://careers\.arm\.com/job/([^/]+)/([^/]+)/\d+/\d+/?$")
# words a slug lower-cases that read wrongly in title case
_ARM_ACRONYMS = {
    "ai", "ml", "gpu", "cpu", "npu", "soc", "ip", "qa", "fpga", "rtl", "rf", "dft", "eda", "hpc",
    "it", "uk", "ui", "ux", "hr", "pr", "os", "sw", "hw", "ic", "asic", "vlsi", "devops",
}


def _slug_words(slug: str) -> str:
    return " ".join(
        w.upper() if w in _ARM_ACRONYMS else w.capitalize()
        for w in slug.split("-") if w
    )


def parse_arm_sitemap(xml_text: str) -> list[tuple[str, str, str]]:
    """(title, city, url) for every job page the sitemap lists, in sitemap order.

    Job pages sit at /job/{city}/{title-slug}/{org}/{id}; the category and landing
    pages the sitemap also carries are skipped.
    """
    jobs = []
    seen = set()
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text or ""):
        m = _ARM_JOB_RE.match(loc)
        if not m or loc in seen:
            continue
        seen.add(loc)
        jobs.append((_slug_words(m.group(2)), _slug_words(m.group(1)), loc))
    return jobs


def scrape_arm_sitemap(ctx) -> int:
    """Read Arm's job pages from its sitemap and keep the UK student tech roles.

    The same rule as the old results-page reader: is_relevant on the title and city,
    a role whose URL is already stored is left alone and new rows stop at the
    Arm cap in config.MAX_NEW_PER_SOURCE.
    """
    resp = SESSION.get(ARM_SITEMAP, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"     ARM sitemap: HTTP {resp.status_code}")
        return 0
    count = 0
    for title, city, url in parse_arm_sitemap(resp.content.decode("utf-8-sig", "replace")):
        if not is_relevant(title, "ARM", city):
            continue
        key = dedupe_key("ARM", title, url)
        if key in ctx.existing_keys:
            continue
        if insert_job(ctx, {
            "company": "ARM",
            "role": title,
            "location": normalize_location(city),
            "url": url,
            "type": resolve_type(title),
            "cv_required": True,
            "cap_key": "Arm",
        }):
            count += 1
        ctx.existing_keys.add(key)
    return count


def run(ctx) -> int:
    try:
        return scrape_company_sites_playwright(ctx)
    except Exception as e:
        print(f"  Error company career sites: {e}")
        return 0
