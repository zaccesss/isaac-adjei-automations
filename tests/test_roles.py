# tests/test_roles.py
#
# the shared role rules, run against real titles from the dashboard. Vitafolio's RoleTypeTest runs
# the same titles, so a change on one side shows up as a failure here until both agree.

from datetime import datetime, timezone

import pytest

from scraper.roles import classify, in_cycle

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


@pytest.mark.parametrize("title, kind", [
    ("Software Engineering Internship", "internship"),
    ("Summer Analyst 2027", "internship"),
    ("International Trade Intern", "internship"),
    ("Industrial Placement Year 2026/27", "placement"),
    ("12 Month Placement - Electronic Engineering", "placement"),
    ("Spring Insight Week 2027", "insight"),
    ("Graduate Software Engineer", "graduate"),
    ("Technology Graduate Programme 2027", "graduate"),
    ("Entry-Level Data Analyst", "graduate"),
    ("Internal Audit Manager", None),
    ("Internal Communications Executive", None),
    ("Senior Graduate Recruiter", None),
    ("Placement Coordinator", None),
    ("Replacement Window Fitter", None),
    ("Postgraduate Research Fellow", None),
    ("Degree Apprenticeship in Software", "apprenticeship"),
    ("Apprenticeship Programme Manager", None),
    ("Senior Software Engineer", None),
    ("12 month contract - Project Manager", None),
    ("2026 Machine Learning Center of Excellence (NLP)-Internship", "internship"),
    ("12 months Placement- Back-End Developer (Internship) starting July 2027", "placement"),
    ("Network Engineer Intern (12 Months)", "placement"),
    ("Controls Systems Industrial Placements", "placement"),
    ("Tech Insight Experience for Women - Engineering", "insight"),
    ("Discovery Week", "insight"),
    ("2027 Full-Time Analyst Programme - Client and Product Functions", "graduate"),
    ("Investment Banking 2027 Off-cycle Analyst - London", "internship"),
    ("Quant Research Associate Programme", "graduate"),
    ("Post-graduate Teaching Assistant", None),
    ("Junior Software Engineer", None),
    ("Campus - Full Time - Software Engineer - 2027 (UK - Burgess Hill)", "graduate"),
])
def test_titles_are_classified_by_whole_words(title, kind):
    assert classify(title) == kind


def test_the_cycle_rejects_past_years_and_finished_seasons():
    assert in_cycle("Graduate Engineer", NOW)
    assert in_cycle("Summer Internship 2027", NOW)
    assert in_cycle("Placement 2026-27", NOW)
    assert in_cycle("Undergraduate Placement Year 2027-28", NOW)
    assert in_cycle("Technology Analyst Graduate Programme 2027 - 2028", NOW)
    assert not in_cycle("Summer Internship 2026", NOW)
    assert not in_cycle("Graduate Scheme 2025", NOW)
    assert not in_cycle("Graduate Programme 2028", NOW)
    assert not in_cycle("Placement 2025/26", NOW)
    assert not in_cycle("Graduate Programme 2028 - 2029", NOW)
