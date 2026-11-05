from scraper.db import normalize_work_mode


def test_known_spellings_share_one_label():
    assert normalize_work_mode("hybrid") == "Hybrid"
    assert normalize_work_mode("Remote") == "Remote"
    for raw in ("onsite", "On-site", "ON_SITE", "in office", " office "):
        assert normalize_work_mode(raw) == "Onsite"


def test_empty_and_unknown_values():
    assert normalize_work_mode(None) == ""
    assert normalize_work_mode("") == ""
    assert normalize_work_mode("Flexible") == "Flexible"
