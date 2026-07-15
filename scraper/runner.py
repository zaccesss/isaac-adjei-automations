"""Orchestrates the sources in their long-standing order, honouring SCRAPER_MODE and the time budget."""
from datetime import datetime

from . import config, db, stats
from .budget import over_budget
from .context import RunContext
from .notify import send_discord_alert
from .sources import SOURCES


def main():
    print(f"Job scraper starting at {datetime.now().isoformat()} (SCRAPER_MODE={config.SCRAPER_MODE})")

    ctx = RunContext.create()

    # I load the existing keys (and the URL set) up front so insert_job knows whether
    # to insert a new row or refresh an existing one. Nothing is ever deleted - the
    # scraper only inserts and updates.
    db.load_existing_keys(ctx)
    print(f"Found {len(ctx.existing_keys)} existing applications in DB")

    total = 0
    for name, mode, gated, run in SOURCES:
        if config.SCRAPER_MODE not in (mode, "all"):
            continue
        # The old main wrapped only the later API sources in a budget check; the
        # browser pair and the first four API families manage the budget internally,
        # so only the gated sources are skipped here (skipped, not aborted, exactly
        # as before).
        if gated and over_budget(ctx):
            continue
        total += run(ctx)

    # I refresh last_scraped_at for everything seen this run, without touching any
    # user-set field. The scraper never deletes rows, so this is purely a freshness
    # stamp. It runs in the api and all modes only, exactly where the old main
    # left it.
    if config.SCRAPER_MODE in ("api", "all"):
        db.refresh_seen_timestamps(ctx)

    # I send a Discord alert with all newly found student roles so I know what came
    # in from today's run without waiting for the Sunday digest.
    if ctx.new_jobs:
        print(f"\nSending Discord alert for {len(ctx.new_jobs)} new student roles...")
        send_discord_alert(ctx.new_jobs)

    print(f"\nDone. Added {total} new jobs.")

    stats.write_summary(ctx)
