# Cases derived from the inline comments in scraper/db.py: URL-based keys beat
# company+role, the Greenhouse domain migration hashes identically and the no-URL
# fallback is case-insensitive.
from scraper.db import dedupe_key


def test_both_greenhouse_domains_hash_identically():
    old = dedupe_key("X", "Y", "https://boards.greenhouse.io/acme/jobs/1")
    new = dedupe_key("X", "Y", "https://job-boards.greenhouse.io/acme/jobs/1")
    assert old == new


def test_trailing_slashes_do_not_split_keys():
    assert dedupe_key("X", "Y", "https://a.example/jobs/1") == dedupe_key("X", "Y", "https://a.example/jobs/1/")


def test_the_url_wins_over_company_and_role():
    a = dedupe_key("Acme", "Intern", "https://a.example/jobs/1")
    b = dedupe_key("Different Name", "Other Role", "https://a.example/jobs/1")
    assert a == b


def test_the_no_url_fallback_is_case_insensitive():
    assert dedupe_key("Google", "SWE Intern") == dedupe_key("google", "swe intern")
    assert dedupe_key("Google", "SWE Intern") != dedupe_key("Google", "Data Intern")
