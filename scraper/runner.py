"""Orchestrates the sources in their long-standing order, honouring SCRAPER_MODE and the time budget."""

import os
from datetime import datetime
from . import db
from . import stats
from .ai import GOOGLE_AI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, ai_extract
from .budget import _over_budget
from .config import SCRAPER_MODE
from .data.companies import ASHBY_COMPANIES, GREENHOUSE_COMPANIES, LEVER_COMPANIES, SMARTRECRUITERS_COMPANIES
from .db import load_existing_keys, refresh_seen_timestamps
from .notify import send_discord_alert
from .sources.adzuna import scrape_adzuna
from .sources.amazon import scrape_amazon
from .sources.apple import scrape_apple
from .sources.arbeitnow import scrape_arbeitnow
from .sources.ashby import scrape_ashby
from .sources.company_sites import scrape_company_sites_playwright
from .sources.greenhouse import scrape_greenhouse
from .sources.jobicy import scrape_jobicy
from .sources.jooble import scrape_jooble
from .sources.lever import scrape_lever
from .sources.microsoft import scrape_microsoft
from .sources.reed import scrape_reed
from .sources.remotive import scrape_remotive
from .sources.smartrecruiters import scrape_smartrecruiters
from .sources.trackr import scrape_trackr_all
from .sources.workday import WORKDAY_COMPANIES, scrape_workday
from .stats import _record_stat

# ─── MAIN ───────────────────────────────────────────────────────────────────


def main():
    # Fresh run state, cleared in place: these sets live in the db module now and
    # nothing else holds a reference at this point, so clearing equals rebinding.
    db._seen_urls.clear()
    db._new_jobs.clear()

    # Quick AI self-test: SCRAPER_AI_TEST runs the extractor on a sample advert and exits, so I can
    # confirm the providers and JSON parsing work without a full scrape.
    if os.environ.get("SCRAPER_AI_TEST", "").strip():
        sample = (
            "Graduate Embedded Software Engineer at a London fintech startup. We design custom FPGA "
            "and firmware for low-latency trading hardware in C++ and Rust. Salary GBP 50,000 to "
            "60,000. Hybrid, three days in the office. We sponsor Skilled Worker visas for strong "
            "candidates. A cover letter is required. Apply by 2026-09-30."
        )
        print("AI keys present -> groq:", bool(GROQ_API_KEY), "gemini:", bool(GOOGLE_AI_API_KEY), "openrouter:", bool(OPENROUTER_API_KEY))
        print("AI test result:", ai_extract(sample, "Graduate Embedded Software Engineer", "FinTech Startup"))
        return

    print(f"Job scraper starting at {datetime.now().isoformat()} (SCRAPER_MODE={SCRAPER_MODE})")

    # I load the existing keys (and the URL set) up front so insert_job knows whether to insert a new
    # row or refresh an existing one. Nothing is ever deleted - the scraper only inserts and updates.
    existing_keys = load_existing_keys()
    print(f"Found {len(existing_keys)} existing applications in DB")

    total = 0

    # I only run Playwright scrapers in browser or all mode.
    if SCRAPER_MODE in ("browser", "all"):
        try:
            n = scrape_trackr_all(existing_keys)
            total += n
            _record_stat("The Trackr", n)
        except Exception as e:
            # I guard the call site too because an uncaught exception here would
            # abort the whole run - the try/except inside scrape_trackr_all only
            # catches per-category errors, not startup failures.
            print(f"  Error The Trackr: {e}")
            _record_stat("The Trackr", 0, str(e))

        try:
            n = scrape_company_sites_playwright(existing_keys)
            total += n
        except Exception as e:
            print(f"  Error company career sites: {e}")

    # I run all API scrapers when SCRAPER_MODE is api or all.
    if SCRAPER_MODE in ("api", "all"):
        # I run the JSON API scrapers because they are the most reliable and
        # fastest - no HTML parsing involved.
        print("\n--- Greenhouse ---")
        gh_total = 0
        for slug, name in GREENHOUSE_COMPANIES:
            if _over_budget():
                print("  [budget] skipping remaining Greenhouse companies")
                break
            n = scrape_greenhouse(slug, name, existing_keys)
            if n:
                print(f"  {name}: {n}")
            gh_total += n
        total += gh_total
        _record_stat("Greenhouse", gh_total)

        print("\n--- Lever ---")
        lv_total = 0
        for slug, name in LEVER_COMPANIES:
            if _over_budget():
                print("  [budget] skipping remaining Lever companies")
                break
            n = scrape_lever(slug, name, existing_keys)
            if n:
                print(f"  {name}: {n}")
            lv_total += n
        total += lv_total
        _record_stat("Lever", lv_total)

        print("\n--- Ashby ---")
        ab_total = 0
        for slug, name in ASHBY_COMPANIES:
            if _over_budget():
                print("  [budget] skipping remaining Ashby companies")
                break
            n = scrape_ashby(slug, name, existing_keys)
            if n:
                print(f"  {name}: {n}")
            ab_total += n
        total += ab_total
        _record_stat("Ashby", ab_total)

        print("\n--- SmartRecruiters ---")
        sr_total = 0
        for company_id, name in SMARTRECRUITERS_COMPANIES:
            if _over_budget():
                print("  [budget] skipping remaining SmartRecruiters companies")
                break
            n = scrape_smartrecruiters(company_id, name, existing_keys)
            if n:
                print(f"  {name}: {n}")
            sr_total += n
        total += sr_total
        _record_stat("SmartRecruiters", sr_total)

        if not _over_budget():
            print("\n--- Apple Careers ---")
            try:
                n = scrape_apple(existing_keys)
                total += n
                _record_stat("Apple Careers", n)
            except Exception as e:
                print(f"  Error Apple: {e}")
                _record_stat("Apple Careers", 0, str(e))

        if not _over_budget():
            print("\n--- Microsoft Careers ---")
            try:
                n = scrape_microsoft(existing_keys)
                total += n
                _record_stat("Microsoft Careers", n)
            except Exception as e:
                print(f"  Error Microsoft: {e}")
                _record_stat("Microsoft Careers", 0, str(e))

        if not _over_budget():
            print("\n--- Amazon Jobs ---")
            try:
                n = scrape_amazon(existing_keys)
                total += n
                _record_stat("Amazon Jobs", n)
            except Exception as e:
                print(f"  Error Amazon: {e}")
                _record_stat("Amazon Jobs", 0, str(e))

        if not _over_budget():
            print("\n--- Workday (NVIDIA / Intel / Morgan Stanley) ---")
            wd_total = 0
            for subdomain, wdnum, tenant, site_id, name in WORKDAY_COMPANIES:
                if _over_budget():
                    break
                try:
                    n = scrape_workday(subdomain, wdnum, tenant, site_id, name, existing_keys)
                    wd_total += n
                except Exception as e:
                    print(f"  Error {name} Workday: {e}")
            total += wd_total
            _record_stat("Workday", wd_total)

        if not _over_budget():
            print("\n--- Reed ---")
            n = scrape_reed(existing_keys)
            total += n
            _record_stat("Reed", n)

        if not _over_budget():
            print("\n--- Adzuna ---")
            n = scrape_adzuna(existing_keys)
            total += n
            _record_stat("Adzuna", n)

        if not _over_budget():
            print("\n--- Jooble ---")
            n = scrape_jooble(existing_keys)
            total += n
            _record_stat("Jooble", n)

        if not _over_budget():
            print("\n--- Arbeitnow ---")
            n = scrape_arbeitnow(existing_keys)
            total += n
            _record_stat("Arbeitnow", n)

        if not _over_budget():
            print("\n--- Jobicy ---")
            n = scrape_jobicy(existing_keys)
            total += n
            _record_stat("Jobicy", n)

        if not _over_budget():
            n = scrape_remotive(existing_keys)
            total += n
            _record_stat("Remotive", n)

        # I refresh last_scraped_at for everything seen this run, without touching any user-set
        # field. The scraper never deletes rows, so this is purely a freshness stamp.
        refresh_seen_timestamps()

    # I send a Discord alert with all newly found student roles so I know
    # what came in from today's run without waiting for the Sunday digest.
    if db._new_jobs:
        print(
            f"\nSending Discord alert for {len(db._new_jobs)} new student roles..."
        )
        send_discord_alert(db._new_jobs)

    print(f"\nDone. Added {total} new jobs.")

    # I write a Markdown summary table to source-stats.md so the workflow can
    # cat it into $GITHUB_STEP_SUMMARY and make failures visible at a glance.
    if stats._source_stats:
        # I write to source-stats.md regardless of whether GITHUB_STEP_SUMMARY
        # is set so the file can be inspected locally too.
        lines = [
            "| Source | Rows added | Note |",
            "|---|---|---|",
        ]
        for stat in stats._source_stats:
            # I coerce None note to empty string for cleaner table output.
            note = stat.get("note") or ""
            lines.append(f"| {stat['source']} | {stat['rows']} | {note} |")
        summary_text = "\n".join(lines) + "\n"
        with open("source-stats.md", "w") as fh:
            fh.write(summary_text)
