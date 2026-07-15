# Cases derived from the inline comments in scraper/dates.py: the 14 day grace window
# for freshly closed roles, the per-type cutoffs and every Trackr date format.
from datetime import datetime, timedelta

from scraper.dates import (
    CYCLE_CUTOFF,
    JOB_CUTOFF,
    _parse_greenhouse_date,
    _parse_trackr_date,
    is_date_relevant,
)


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def test_missing_or_malformed_deadlines_are_included():
    assert is_date_relevant(None)
    assert is_date_relevant("")
    assert is_date_relevant("rolling deadline")


def test_the_cycle_cutoff_drops_last_seasons_roles():
    assert not is_date_relevant("2025-08-01")
    assert is_date_relevant(_iso(datetime.now() + timedelta(days=30)))


def test_the_grace_window_keeps_freshly_closed_roles():
    assert is_date_relevant(_iso(datetime.now() - timedelta(days=7)))
    assert not is_date_relevant(_iso(datetime.now() - timedelta(days=30)))


def test_the_cutoffs_sit_at_the_2026_season_line():
    # Both cutoffs sit at Jan 2026 this season (the owner moved the cycle cutoff up:
    # 2025-dated roles are stale). is_date_relevant must honour whichever it is given.
    assert CYCLE_CUTOFF == datetime(2026, 1, 1)
    assert JOB_CUTOFF == datetime(2026, 1, 1)
    assert not is_date_relevant("2025-12-01")
    assert is_date_relevant(_iso(datetime.now() + timedelta(days=30)), JOB_CUTOFF)


def test_every_trackr_date_format_parses():
    assert _parse_trackr_date("21 May 26") == "2026-05-21"
    assert _parse_trackr_date("21 May 2026") == "2026-05-21"
    assert _parse_trackr_date("21/05/2026") == "2026-05-21"
    assert _parse_trackr_date("21/05/26") == "2026-05-21"
    assert _parse_trackr_date("21 May 2026 ") == "2026-05-21"
    assert _parse_trackr_date("2026-05-21") == "2026-05-21"


def test_trackr_placeholders_return_none():
    assert _parse_trackr_date(None) is None
    assert _parse_trackr_date("") is None
    assert _parse_trackr_date("TBC") is None
    assert _parse_trackr_date("rolling") is None
    assert _parse_trackr_date("-") is None


def test_greenhouse_timestamps_become_plain_dates():
    assert _parse_greenhouse_date("2026-01-15T08:12:57-04:00") == "2026-01-15"
    assert _parse_greenhouse_date(None) is None
