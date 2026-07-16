# SCRAPER_DRY_RUN=1 rehearses a run: the write paths print and collect instead of
# touching Supabase. The context here carries no client at all, so any accidental
# database call would fail the test immediately.
from scraper import config
from scraper.context import RunContext
from scraper.db import insert_job, refresh_seen_timestamps


def test_dry_run_inserts_collect_instead_of_writing(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    ctx = RunContext.bare()

    # No URL, so no liveness check fires; no description, so no AI call fires.
    job = {"company": "Acme", "role": "Software Intern", "type": "Internship", "deadline": None}
    assert insert_job(ctx, job) is True

    assert ctx.dry_run_actions == [("insert", "Acme", "Software Intern")]
    assert ctx.new_jobs == [job]

    # The second pass classifies it as already known, exactly like a real run.
    assert insert_job(ctx, dict(job)) is False
    assert len(ctx.dry_run_actions) == 1


def test_dry_run_update_path_and_timestamp_refresh(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    ctx = RunContext.bare()
    ctx.existing_urls.add("https://a.example/jobs/1")

    job = {
        "company": "Acme",
        "role": "Software Intern",
        "type": "Internship",
        "url": "https://a.example/jobs/1",
        "deadline": None,
    }
    assert insert_job(ctx, job) is False
    assert ctx.dry_run_actions == [("update", "Acme", "Software Intern")]
    assert "https://a.example/jobs/1" in ctx.seen_urls

    # The freshness stamp prints rather than writing; no client, so a write would raise.
    refresh_seen_timestamps(ctx)


def test_dry_run_defaults_off():
    assert config.DRY_RUN is False


def test_a_linked_row_heals_the_urlless_original_instead_of_duplicating(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    ctx = RunContext.bare()

    # The url-less original was inserted in an earlier run.
    original = {"company": "Acme", "role": "Software Intern", "type": "Internship", "deadline": None}
    assert insert_job(ctx, original) is True

    # The same row arrives again, now carrying a fallback link: it must fill the
    # URL onto the original, not insert a linked twin (the fragment URL changes
    # the url-based dedupe key, which is exactly how the twins happened).
    linked = dict(original)
    linked["url"] = "https://app.the-trackr.com/company/acme#Software%20Intern"
    assert insert_job(ctx, linked) is False
    assert ("fill-url", "Acme", "Software Intern") in ctx.dry_run_actions
    assert len([a for a in ctx.dry_run_actions if a[0] == "insert"]) == 1
