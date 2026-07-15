# Cases derived from the inline comments in scraper/locations.py: bare-city
# normalisation, the ", us" suffix rejection, the remote-US variants and the priority
# company allowance for unrecognised foreign locations.
from scraper.locations import is_location_ok, normalize_location


def test_bare_uk_cities_gain_the_country_suffix():
    assert normalize_location("London") == "London, UK"
    assert normalize_location("Birmingham") == "Birmingham, UK"


def test_already_suffixed_locations_are_left_alone():
    assert normalize_location("London, UK") == "London, UK"
    assert normalize_location("Remote") == "Remote"
    assert normalize_location("") == ""


def test_unknown_locations_are_included():
    assert is_location_ok("", False)


def test_uk_and_london_districts_are_accepted():
    assert is_location_ok("London, UK", False)
    assert is_location_ok("Paddington, London", False)
    assert is_location_ok("Hybrid - Manchester", False)


def test_us_locations_are_rejected():
    assert not is_location_ok("New York", False)
    assert not is_location_ok("remote - us", False)
    assert not is_location_ok("Springfield, US", False)
    # US rejection holds even for priority companies.
    assert not is_location_ok("San Francisco, California", True)


def test_priority_companies_keep_unrecognised_foreign_locations():
    assert not is_location_ok("Lagos", False)
    assert is_location_ok("Lagos", True)
