# the November 2026 sources: Gradcracker's electronics listings, Thales and the
# UKESF partner companies, the Arm sitemap and Imagination's PageUp feed. These
# pin the stricter title and UK guard, the per-source cap, the alert's priority
# order and each new parser against a compact fixture. No test touches the network.
from datetime import date

import pytest

from scraper import config
from scraper.context import RunContext
from scraper.db import insert_job
from scraper.filters import has_engineering_title, is_expired, passes_new_source_guard
from scraper.locations import priority_rank
from scraper.notify import alert_line, order_for_alert
from scraper.sources import bamboohr, eightfold_pcsx, imagination, workday, wordpress_jobs
from scraper.sources import gradcracker as gc
from scraper.sources.company_sites import parse_arm_sitemap


# ─── The discipline filter ──────────────────────────────────────────────────

@pytest.mark.parametrize("title", [
    "Electronics Engineer Placement",
    "Embedded Software Intern",
    "FPGA Design Engineering Internship",
    "RF Engineer - Summer Placement 2027",
    "Avionics Systems Graduate",
    "2027 Systems Engineering Graduate",
    "Controls Engineer Industrial Placement",
    "Electrical Manufacturing Engineer Intern",
    "Power Electronics Undergraduate Placement",
])
def test_electronics_and_computing_titles_pass(title):
    assert has_engineering_title(title), title


@pytest.mark.parametrize("title", [
    "Mechanical Engineering Placement",
    "Graduate Civil Engineer",
    "Chemical Process Engineer Intern",
    "2027 Bid & Project Management Office Graduate",
    "Manufacturing Systems Engineer Placement",
    "Mechanical Test Engineer Placement",
    "Finance Graduate Programme",
    "Supportability Engineering Graduate",
])
def test_other_disciplines_fail(title):
    assert not has_engineering_title(title), title


def test_rf_is_a_whole_word():
    assert not has_engineering_title("Performance Placement")


def test_guard_needs_a_student_role_in_the_uk_that_is_still_open():
    today = date(2026, 11, 5)
    ok = dict(company="Thales", location="Crawley, United Kingdom", today=today)
    assert passes_new_source_guard("2027 Software Engineering Graduate", **ok)
    # full-time roles never pass, even in scope
    assert not passes_new_source_guard("Software Engineer", **ok)
    # UK only, judged by is_uk
    assert not passes_new_source_guard("Software Engineer Intern", "Thales", "Singapore", today=today)
    assert not passes_new_source_guard("Software Engineer Intern", "Thales", "", today=today)
    # a closing date already past drops the role; today and later keep it
    assert not passes_new_source_guard("Software Engineer Intern", closing="2026-11-04", **ok)
    assert passes_new_source_guard("Software Engineer Intern", closing="2026-11-05", **ok)
    # a department signal stands in for a title with no student term
    assert passes_new_source_guard("GPU Verification Engineer", "Imagination Technologies", "Bristol UK",
                                   dept_names=["Early Career"], today=today)


def test_is_expired_ignores_missing_or_odd_dates():
    assert not is_expired(None)
    assert not is_expired("rolling")
    assert is_expired("2026-01-01T00:00:00Z", today=date(2026, 11, 5))


def test_gradcracker_electronics_reject_is_looser_than_computing():
    # avionics and defence titles filed under aerospace stay in for electronics only
    assert gc._NON_COMPUTING_RE.search("Aerospace Avionics Engineer Placement")
    assert not gc._NON_ELECTRONICS_RE.search("Aerospace Avionics Engineer Placement")
    for title in ["Mechanical Design Placement", "Graduate Civil Engineer", "Chemical Engineering Intern"]:
        assert gc._NON_ELECTRONICS_RE.search(title), title
    # the computing listings keep their original list
    assert gc.LISTINGS == [
        "/search/computing-technology/internships-work-placements",
        "/search/computing-technology/jobs",
    ]


# ─── The per-source cap ─────────────────────────────────────────────────────

def _dry_ctx(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    import scraper.db as db
    monkeypatch.setattr(db, "is_url_alive", lambda url: True)
    return RunContext(supabase=None)


def _job(n, cap_key="Thales"):
    return {
        "company": "Thales", "role": f"Software Engineer Intern {n}", "type": "Internship",
        "url": f"https://thales.example/jobs/{n}", "location": "Crawley, UK", "source": "Workday",
        "cap_key": cap_key,
    }


def test_cap_stops_new_rows_but_existing_urls_still_refresh(monkeypatch):
    ctx = _dry_ctx(monkeypatch)
    monkeypatch.setitem(config.MAX_NEW_PER_SOURCE, "Thales", 2)
    ctx.existing_urls.add("https://thales.example/jobs/9")
    assert insert_job(ctx, _job(1)) is True
    assert insert_job(ctx, _job(2)) is True
    assert insert_job(ctx, _job(3)) is False
    assert ctx.new_by_cap["Thales"] == 2
    assert ctx.gate_rejects["over its source cap"] == 1
    # a known URL still takes the refresh path once the cap is full
    assert insert_job(ctx, _job(9)) is False
    assert ("update", "Thales", "Software Engineer Intern 9") in ctx.dry_run_actions


def test_cap_counts_each_source_separately_and_leaves_uncapped_jobs_alone(monkeypatch):
    ctx = _dry_ctx(monkeypatch)
    monkeypatch.setitem(config.MAX_NEW_PER_SOURCE, "Thales", 1)
    assert insert_job(ctx, _job(1)) is True
    assert insert_job(ctx, _job(2)) is False
    # a job from an existing source carries no cap_key and is never capped
    for n in range(3, 6):
        assert insert_job(ctx, _job(n, cap_key=None)) is True


def test_every_cap_named_in_the_brief_is_set():
    caps = config.MAX_NEW_PER_SOURCE
    assert caps["Gradcracker EE"] == 30
    assert caps["Thales"] == 15
    assert caps["Arm"] == 10
    assert caps["Imagination Technologies"] == 5
    assert caps["Raspberry Pi"] == 5


# ─── The alert's priority order ─────────────────────────────────────────────

def test_priority_rank():
    assert priority_rank("London, UK", "Google", "Software Engineering Intern") == 0
    assert priority_rank("London, UK", "Thales", "Software Engineering Intern") == 1
    assert priority_rank("Birmingham, UK", "Google", "Software Intern") == 2
    assert priority_rank("Stevenage", "MBDA", "Electronics Placement") == 2
    assert priority_rank("Milton Keynes", "Acme", "Software Intern") == 2
    assert priority_rank("Bristol, UK", "Acme", "Software Intern") == 3
    assert priority_rank("", "Acme", "Software Intern") == 3
    # London, Ontario is not London
    assert priority_rank("London, Ontario, Canada", "Google", "Software Intern") == 3


def test_alert_orders_by_rank_and_labels_the_top_ranks():
    jobs = [
        {"company": "Acme", "role": "Software Intern", "type": "Internship", "url": "u1", "location": "Bristol"},
        {"company": "MBDA", "role": "Electronics Placement", "type": "Industrial Placement", "url": "u2",
         "location": "Stevenage"},
        {"company": "Thales", "role": "Software Intern", "type": "Internship", "url": "u3", "location": "London"},
        {"company": "Google", "role": "Software Intern", "type": "Internship", "url": "u4", "location": "London, UK"},
    ]
    ordered = order_for_alert(jobs)
    assert [j["company"] for j in ordered] == ["Google", "Thales", "MBDA", "Acme"]
    lines = [alert_line(j) for j in ordered]
    assert lines[0].startswith("- Top priority: **Internship**")
    assert lines[1].startswith("- Priority location: ")
    assert lines[2].startswith("- Priority location: ")
    # everywhere else keeps the original line exactly
    assert lines[3] == "- **Internship** [Acme - Software Intern](u1)"


# ─── The new parsers ────────────────────────────────────────────────────────

ARM_SITEMAP = """﻿<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://careers.arm.com</loc></url>
<url><loc>https://careers.arm.com/category/software-engineering-jobs/33099/8081696/1</loc></url>
<url><loc>https://careers.arm.com/job/cambridge/graduate-ml-software-engineer/33099/102806620832</loc></url>
<url><loc>https://careers.arm.com/job/milton-keynes/gpu-compiler-intern/33099/102539121920</loc></url>
<url><loc>https://careers.arm.com/job/cambridge/graduate-ml-software-engineer/33099/102806620832</loc></url>
</urlset>"""


def test_arm_sitemap_reads_title_and_city_from_job_urls():
    assert parse_arm_sitemap(ARM_SITEMAP) == [
        ("Graduate ML Software Engineer", "Cambridge",
         "https://careers.arm.com/job/cambridge/graduate-ml-software-engineer/33099/102806620832"),
        ("GPU Compiler Intern", "Milton Keynes",
         "https://careers.arm.com/job/milton-keynes/gpu-compiler-intern/33099/102539121920"),
    ]
    assert parse_arm_sitemap("") == []


PAGEUP_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel xmlns:job="http://pageuppeople.com/">
<item><link>https://careers.pageuppeople.com/774/cw/en/job/1</link><title>GPU Verification Engineer</title>
<job:location>Bristol UK</job:location><job:closingDate>30/11/2026</job:closingDate>
<job:workType>Early Career</job:workType></item>
<item><link>https://careers.pageuppeople.com/774/cw/en/job/2</link><title>Legal Counsel</title>
<job:location>Kings Langley UK,Bristol UK</job:location><job:closingDate></job:closingDate>
<job:workType>Experienced Professional</job:workType></item>
</channel></rss>"""


def test_imagination_feed_fields():
    items = imagination.parse_feed(PAGEUP_RSS)
    assert items[0] == {
        "title": "GPU Verification Engineer",
        "url": "https://careers.pageuppeople.com/774/cw/en/job/1",
        "location": "Bristol UK",
        "closing": "2026-11-30",
        "work_types": ["Early Career"],
    }
    assert items[1]["closing"] is None
    assert items[1]["work_types"] == ["Experienced Professional"]


def test_bamboohr_openings():
    payload = {"result": [
        {"id": "232", "jobOpeningName": "Verification Engineer", "departmentLabel": "UK Verification",
         "location": {"city": "Cambridge", "state": "Cambridgeshire"}, "atsLocation": {"country": None}},
        {"id": "220", "jobOpeningName": "Talent pool", "departmentLabel": None,
         "location": {"city": None, "state": None}, "atsLocation": {}},
    ]}
    jobs = bamboohr.parse_openings(payload, "codasip")
    assert jobs[0] == {"title": "Verification Engineer", "url": "https://codasip.bamboohr.com/careers/232",
                       "location": "Cambridge, Cambridgeshire", "depts": ["UK Verification"]}
    assert jobs[1]["location"] == "" and jobs[1]["depts"] is None


def test_eightfold_pcsx_positions():
    payload = {"data": {"count": 1, "positions": [{
        "name": "FY27 Intern - Formal Verification Engineering Internship ",
        "standardizedLocations": ["Cambridge, England, GB"], "department": "Engineering",
        "positionUrl": "/careers/job/123",
    }]}}
    assert eightfold_pcsx.parse_positions(payload, "careers.qualcomm.com") == [{
        "title": "FY27 Intern - Formal Verification Engineering Internship",
        "url": "https://careers.qualcomm.com/careers/job/123",
        "location": "Cambridge, England, GB",
        "depts": ["Engineering"],
    }]


def test_wordpress_titles_are_unescaped():
    posts = [{"title": {"rendered": "Electronics Engineer &#8211; Placement"}, "link": "https://x.example/v/1/"}]
    assert wordpress_jobs.parse_posts(posts) == [
        {"title": "Electronics Engineer " + chr(8211) + " Placement", "url": "https://x.example/v/1/"},
    ]


# ─── Existing Workday tenants are untouched ────────────────────────────────

def test_existing_workday_payload_is_unchanged(monkeypatch):
    sent = []

    class _Resp:
        status_code = 200

        def json(self):
            return {"total": 0, "jobPostings": []}

    monkeypatch.setattr(workday.SESSION, "post", lambda url, json, headers, timeout: sent.append(json) or _Resp())
    workday.scrape_workday(RunContext(supabase=None), "nvidia", "5", "nvidia", "NVIDIAExternalCareerSite", "NVIDIA")
    assert sent == [{"limit": 20, "offset": 0, "searchText": "intern"}]
    # only the newer tenants carry options
    assert set(workday.WORKDAY_OPTIONS) <= set(config.MAX_NEW_PER_SOURCE)
