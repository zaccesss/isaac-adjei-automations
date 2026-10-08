# tests/test_gate.py
#
# the final check every role passes before it reaches the dashboard: the shared role rules, the
# recruitment cycle and UK only, with a blank location trusted only from a UK-only board.

from scraper.db import company_key, dedupe_key, gate
from scraper.locations import MULTI_LOCATION_RE


def job(role="Software Engineering Intern", location="London", source="Greenhouse"):
    return {"role": role, "location": location, "source": source}


def test_a_uk_student_role_in_the_cycle_passes():
    assert gate(job()) is None
    assert gate(job(location="Fleet, England")) is None
    assert gate(job(location="Berlin; London; Munich")) is None


def test_apprenticeships_and_past_cycles_are_kept_off():
    assert gate(job(role="Level 3 Software Apprenticeship")) == "apprenticeship"
    assert gate(job(role="Software Summer Internship 2026")) == "outside the cycle"
    assert gate(job(role="Graduate Software Scheme 2025")) == "outside the cycle"


def test_student_roles_abroad_are_flagged_and_other_roles_kept_out():
    assert gate(job(location="Fab 10A, Singapore")) == "abroad"
    assert gate(job(location="Sydney, New South Wales, Australia")) == "abroad"
    assert gate(job(location="US, MA, Chelmsford")) == "abroad"
    # an unknown place and full-time roles abroad never reach the dashboard
    assert gate(job(location="2 Locations")) == "outside the UK"
    assert gate(job(location="Remote")) == "outside the UK"
    assert gate(job(role="Senior Software Engineer", location="Fab 10A, Singapore")) == "outside the UK"


def test_a_blank_location_is_trusted_only_from_a_uk_board():
    assert gate(job(location="", source="Gradcracker")) is None
    assert gate(job(location="", source="Greenhouse")) == "outside the UK"


def test_a_place_already_pinned_in_great_britain_counts():
    assert gate(job(location="Cheadle Hulme Business Park"), uk_places={"cheadle hulme business park"}) is None


def test_multi_location_placeholders_are_recognised():
    assert MULTI_LOCATION_RE.match("2 Locations")
    assert MULTI_LOCATION_RE.match("12 locations")
    assert not MULTI_LOCATION_RE.match("London")


def test_non_technical_roles_are_kept_out():
    assert gate(job(role="2027 Human Resources Analyst Summer Internship")) == "not a tech or engineering role"
    assert gate(job(role="Summer Internship")) == "not a tech or engineering role"


def test_a_title_naming_another_country_outranks_the_location():
    assert gate(job(role="Software Engineer Intern, Summer 2027 - United States", location="London, UK")) == "abroad"
    assert gate(job(role="2027 Software Engineer Program - Glasgow, London", location="London, UK")) is None


def test_employer_name_variants_share_one_key():
    assert company_key("Barclays Bank Plc") == company_key("Barclays") == "barclays"
    assert company_key("NXP Semiconductors") == company_key("NXP")
    assert company_key("Man Group plc") == company_key("Man Group")
    assert company_key("Tesco Group") == company_key("Tesco Ireland") == "tesco"
    assert dedupe_key("Snap Inc.", "Machine Learning Engineering Intern") == dedupe_key("Snap", "Machine Learning Engineering Intern")


def test_an_unrecognised_place_is_uk_unless_something_says_abroad():
    for place in ["Brixworth (Northamptonshire)", "Thursley (Surrey) (Hybrid)", "Barrow-in-Furness (Cumbria)", "Bromley", "Cramlington"]:
        assert gate(job(location=place)) is None, place
    assert gate(job(location="Hsinchu")) == "abroad"
    assert gate(job(location="Santa Clara, CA")) == "abroad"
    assert gate(job(role="Senior Software Engineer", location="Taipei")) == "outside the UK"


def test_northern_ireland_is_the_uk():
    assert gate(job(role="Technology Graduate Programme - Northern Ireland - September 2027 intake", location="Belfast, UK")) is None
    assert gate(job(location="Belfast, Northern Ireland")) is None
