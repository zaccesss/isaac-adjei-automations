# The Cloudflare-fronted boards (Gradcracker, Bright Network, Milkround) parse
# server-rendered HTML through curl_cffi. Full parsing is covered by the live
# smoke of parse_listing; here I pin the pure helpers and the classification
# decisions that are easy to regress: deadline parsing, the non-computing reject
# and the type each board assigns.
import pytest

from scraper.sources import brightnetwork as bn
from scraper.sources import gradcracker as gc
from scraper.sources import milkround as mr
from scraper.filters import infer_type


def test_gradcracker_parses_ordinal_dates_and_ignores_rolling():
    assert gc._parse_deadline("30th Sep 2026") == "2026-09-30"
    assert gc._parse_deadline("1st January 2027") == "2027-01-01"
    assert gc._parse_deadline("Ongoing") is None
    assert gc._parse_deadline("") is None


def test_gradcracker_drops_non_computing_engineering():
    assert gc._NON_COMPUTING_RE.search("Graduate Civil Engineer")
    assert gc._NON_COMPUTING_RE.search("Mechanical Placement 2027")
    assert gc._NON_COMPUTING_RE.search("Gradcracker Webinar - Mining")
    # Real tech titles are untouched.
    assert not gc._NON_COMPUTING_RE.search("Graduate Software Engineer")
    assert not gc._NON_COMPUTING_RE.search("Firmware Engineer Placement")


def test_gradcracker_type_from_segment_matches_infer():
    # A graduate-job URL is always a graduate scheme; a placement URL defers to
    # the title, so an intern-worded one is an internship.
    assert infer_type("Summer Internship Programme", default="Internship") == "Internship"
    assert infer_type("Software Engineering Placement", default="Internship") == "Industrial Placement"


def test_brightnetwork_reject_and_deadline():
    assert bn._parse_deadline("21st Jul 2026") == "2026-07-21"
    assert bn._parse_deadline("Rolling deadline") is None
    assert bn._NON_COMPUTING_RE.search("Audit & Accounts Internship")
    assert bn._NON_COMPUTING_RE.search("Production Assistant ITV Academy")
    assert not bn._NON_COMPUTING_RE.search("Software Engineering Internship")


def test_milkround_rejects_totaljobs_spam():
    # The widest reject list, because totaljobs floods a tech search with these.
    for junk in [
        "Graduate Technology Recruitment Consultant",
        "Graduate Role - Animal Nutrition",
        "Graduate Trainee - Radiotherapy",
        "Warehouse Operative",
    ]:
        assert mr._NON_COMPUTING_RE.search(junk), junk
    # The hardware and quant gems survive.
    for keep in [
        "GPU Internship - Platform Architecture",
        "Junior RTL Power Optimisation Engineer",
        "Junior Quantitative Researcher",
    ]:
        assert not mr._NON_COMPUTING_RE.search(keep), keep


def test_milkround_salary_detection():
    assert mr._SALARY_RE.search("£35,000 per annum")
    assert mr._SALARY_RE.search("Competitive")
    assert not mr._SALARY_RE.search("London, UK")
