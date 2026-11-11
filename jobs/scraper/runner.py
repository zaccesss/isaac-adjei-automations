"""Orchestrates the sources in their long-standing order, honouring SCRAPER_MODE and the time budget."""
from datetime import datetime

from . import config, db, stats
from .budget import over_budget
from .context import RunContext
from .notify import send_discord_alert, send_discord_note
from .sources import SOURCES


def main():
    print(f"Job scraper starting at {datetime.now().isoformat()} (SCRAPER_MODE={config.SCRAPER_MODE})")

    ctx = RunContext.create()

    # load the existing keys (and the URL set) up front so insert_job knows whether
    # to insert a new row or refresh an existing one. Nothing is ever deleted - the
    # scraper only inserts and updates.
    db.load_existing_keys(ctx)
    print(f"Found {len(ctx.existing_keys)} existing applications in DB")

    total = 0
    failed = []
    for name, mode, gated, run in SOURCES:
        if config.SCRAPER_MODE not in (mode, "all"):
            continue
        # the old main wrapped only the later API sources in a budget check; the
        # browser pair and the first four API families manage the budget internally,
        # so only the gated sources are skipped here (skipped, not aborted, exactly
        # as before).
        if gated and over_budget(ctx):
            continue
        # one source's network or parse failure must not end the run: a Lever read
        # timeout on 26 October 2026 failed the whole job with every later board
        # unread. The failure is logged here and reported at the end instead
        try:
            total += run(ctx)
        except Exception as exc:
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  {name} failed and was skipped: {type(exc).__name__}: {exc}")

    # refresh last_scraped_at for everything seen this run, without touching any
    # user-set field. The scraper never deletes rows, so this is purely a freshness
    # stamp. It runs in the api and all modes only, exactly where the old main
    # left it.
    if config.SCRAPER_MODE in ("api", "all"):
        db.refresh_seen_timestamps(ctx)
        db.archive_stale(ctx)

    if ctx.gate_rejects:
        print("Kept off the dashboard: " + ", ".join(f"{n} {why}" for why, n in sorted(ctx.gate_rejects.items())))

    if failed:
        summary = ", ".join(f"{n} ({e})" for n, e in failed)
        print(f"Sources that failed this run: {summary}")
        send_discord_note(f"Job scraper: {len(failed)} source(s) failed and were skipped: {summary}")

    # send a Discord alert with all newly found student roles so it is clear what came
    # in from today's run without waiting for the Sunday digest.
    if ctx.new_jobs:
        print(f"\nSending Discord alert for {len(ctx.new_jobs)} new student roles...")
        send_discord_alert(ctx.new_jobs)

    print(f"\nDone. Added {total} new jobs.")

    stats.write_summary(ctx)
