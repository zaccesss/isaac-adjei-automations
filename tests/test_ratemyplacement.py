# The RateMyPlacement source parses an embedded JSON blob, so the pure helpers
# (prefix strip, first-location, ISO deadline guard) are the parts worth pinning.
from scraper.sources.ratemyplacement import (
    TYPE_SLUGS,
    _clean_deadline,
    _first_location,
    _PREREG_PREFIX_RE,
)


def _strip(title: str) -> str:
    return _PREREG_PREFIX_RE.sub("", title.strip()).strip()


def test_prereg_prefix_is_stripped_for_every_dash():
    assert _strip("Register Your Interest - Engineering Placement 2027") == "Engineering Placement 2027"
    assert _strip("Register Your Interest – Industrial Placement") == "Industrial Placement"
    assert _strip("Register Your Interest: Software Engineer Intern") == "Software Engineer Intern"
    # Case-insensitive, and only the leading prefix is removed.
    assert _strip("REGISTER YOUR INTEREST - Data Placement") == "Data Placement"


def test_real_titles_are_left_untouched():
    assert _strip("Software Engineering Placement 2027") == "Software Engineering Placement 2027"
    # "register" mid-title must not be mistaken for the prefix.
    assert _strip("Cash Register Systems Intern") == "Cash Register Systems Intern"


def test_first_location_takes_the_leading_city():
    assert _first_location("Liverpool, Edinburgh, Cambridge") == "Liverpool"
    assert _first_location("London") == "London"
    assert _first_location("") == ""


def test_clean_deadline_keeps_iso_dates_only():
    assert _clean_deadline("2026-01-31") == "2026-01-31"
    assert _clean_deadline("2026-01-31T00:00:00.000Z") == "2026-01-31"
    assert _clean_deadline(None) is None
    assert _clean_deadline("") is None
    assert _clean_deadline("rolling") is None


def test_only_server_filterable_types_are_pulled():
    # The graduate slugs are deliberately excluded because the site ignores them
    # and returns the whole board; these three genuinely filter.
    assert set(TYPE_SLUGS) == {"placement", "internship", "insight-vacation-scheme"}
    assert TYPE_SLUGS["placement"] == "Industrial Placement"
