# The July 2026 source wave: the ATS families (Workable, Recruitee, Personio,
# Jibe), the LinkedIn guest search and the three boards (StudentJob, E4S,
# Prospects, TARGETjobs). Each parser is pinned against a compact fixture built
# from the live page it was written on, and the cross-source URL dedupe is
# exercised through insert_job in dry-run mode.
import json

from scraper import config
from scraper.context import RunContext
from scraper.db import dedupe_key, insert_job, url_rank
from scraper.sources import e4s, linkedin_guest, personio, prospects, studentjob, targetjobs


# ─── The cross-source dedupe ────────────────────────────────────────────────

def _dry_ctx(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    import scraper.db as db
    monkeypatch.setattr(db, "is_url_alive", lambda url: True)
    return RunContext(supabase=None)


def _seed(ctx, company, role, url):
    ctx.existing_keys.add(dedupe_key(company, role, url))
    ctx.existing_urls.add(url)
    ctx.url_by_bare_key[dedupe_key(company, role, "")] = url


def test_same_job_from_a_second_source_is_not_inserted_again(monkeypatch):
    ctx = _dry_ctx(monkeypatch)
    _seed(ctx, "Keysight", "Software Development Placement",
          "https://careers.keysight.com/jobs/12345")
    inserted = insert_job(ctx, {
        "company": "Keysight",
        "role": "Software Development Placement",
        "type": "Industrial Placement",
        "url": "https://uk.linkedin.com/jobs/view/software-development-placement-9",
        "location": "Fleet",
        "source": "LinkedIn",
    })
    assert inserted is False
    assert ("insert", "Keysight", "Software Development Placement") not in ctx.dry_run_actions
    # The direct ATS link stays; the board link never replaces it.
    key = dedupe_key("Keysight", "Software Development Placement", "")
    assert ctx.url_by_bare_key[key] == "https://careers.keysight.com/jobs/12345"


def test_a_direct_link_upgrades_a_stored_board_link(monkeypatch):
    ctx = _dry_ctx(monkeypatch)
    _seed(ctx, "Keysight", "Software Development Placement",
          "https://uk.linkedin.com/jobs/view/software-development-placement-9")
    inserted = insert_job(ctx, {
        "company": "Keysight",
        "role": "Software Development Placement",
        "type": "Industrial Placement",
        "url": "https://careers.keysight.com/jobs/12345",
        "location": "Fleet",
        "source": "Workday",
    })
    assert inserted is False
    assert ("upgrade-url", "Keysight", "Software Development Placement") in ctx.dry_run_actions
    key = dedupe_key("Keysight", "Software Development Placement", "")
    assert ctx.url_by_bare_key[key] == "https://careers.keysight.com/jobs/12345"


def test_url_rank_prefers_direct_links():
    assert url_rank("https://careers.example.com/jobs/1") == 2
    assert url_rank("https://uk.linkedin.com/jobs/view/x-9") == 1
    assert url_rank("https://www.milkround.com/job/123") == 1
    assert url_rank("https://www.prospects.ac.uk/graduate-jobs/x-123456") == 1
    assert url_rank("") == 0


# ─── LinkedIn guest cards ───────────────────────────────────────────────────

_LI_FIXTURE = """
<ul><li><div class="base-card">
<a class="base-card__full-link" href="https://uk.linkedin.com/jobs/view/software-development-placement-at-keysight-4001?refId=x">
<span class="sr-only">Software Development Placement</span></a>
<h3 class="base-search-card__title"> Software Development Placement </h3>
<h4 class="base-search-card__subtitle"><a class="hidden-nested-link" href="#"> Keysight Technologies </a></h4>
<span class="job-search-card__location">Fleet, England, United Kingdom</span>
</div></li></ul>
"""


def test_linkedin_cards_parse_and_strip_tracking_params():
    cards = linkedin_guest.parse_cards(_LI_FIXTURE)
    assert len(cards) == 1
    card = cards[0]
    assert card["role"] == "Software Development Placement"
    assert card["company"] == "Keysight Technologies"
    assert card["location"].startswith("Fleet")
    assert card["url"].endswith("-4001")
    assert "?" not in card["url"]


# ─── TARGETjobs cards ───────────────────────────────────────────────────────

_TJ_FIXTURE = """
<a href="/jobs/graduate-software-engineer-231348?src=x">
<span>Spotlight</span><span>Lockheed Martin UK</span>
<span>Graduate Software Engineer</span><span>Gloucester</span>
<span>£34,000</span><span>12 days to apply</span><span>Save</span></a>
"""


def test_targetjobs_card_reads_company_then_role_and_computes_deadline():
    cards = targetjobs.parse_cards(_TJ_FIXTURE)
    assert len(cards) == 1
    card = cards[0]
    assert card["company"] == "Lockheed Martin UK"
    assert card["role"] == "Graduate Software Engineer"
    assert card["location"] == "Gloucester"
    assert card["salary"] == "£34,000"
    assert card["deadline"] is not None
    assert card["url"] == "https://targetjobs.co.uk/jobs/graduate-software-engineer-231348"


# ─── Prospects labelled cards ───────────────────────────────────────────────

_PROSPECTS_FIXTURE = """
<li><a href="/graduate-jobs/graduate-software-developer-2706000?page=0">Graduate Software Developer</a>
<dl><dt>Employer name</dt><dd>Energy UK</dd>
<dt>Location</dt><dd>London</dd>
<dt>Salary</dt><dd>£30,000</dd></dl></li>
"""


def test_prospects_labelled_fields_parse():
    cards = prospects.parse_cards(_PROSPECTS_FIXTURE)
    assert len(cards) == 1
    card = cards[0]
    assert card["role"] == "Graduate Software Developer"
    assert card["company"] == "Energy UK"
    assert card["location"] == "London"
    assert card["salary"] == "£30,000"
    assert card["url"].endswith("-2706000")


# ─── E4S Apollo cache ───────────────────────────────────────────────────────

def _e4s_page(jobs_state: dict) -> str:
    payload = {"props": {"pageProps": {"__APOLLO_STATE__": jobs_state}}}
    return (
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(payload)
        + "</script>"
    )


def test_e4s_jobs_read_org_deadline_and_strip_prereg_prefix():
    html = _e4s_page({
        "Job:1": {
            "title": "Register Your Interest - Graduate Programme 2027",
            "organization": "kpmg",
            "organizationProfile": {"__ref": "OrganizationProfile:9"},
            "url": {"path": "/job/graduate-programme-1"},
            "absoluteUrl": None,
            "expiration": "2026-09-28T11:05:15+01:00",
            "address": ["United Kingdom"],
            "occupationalField": [{"label": "IT"}],
        },
        "OrganizationProfile:9": {"name": "KPMG"},
    })
    jobs = e4s.parse_jobs(html)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["role"] == "Graduate Programme 2027"
    assert job["company"] == "KPMG"
    assert job["deadline"] == "2026-09-28"
    assert job["url"] == "https://www.e4s.co.uk/job/graduate-programme-1"
    assert job["depts"] == ["IT"]


def test_e4s_rejects_the_survey_and_test_user_spam():
    assert e4s._NON_COMPUTING_RE.search("Become a paid test user for brands")
    assert e4s._NON_COMPUTING_RE.search("PAID GAME TESTERS NEEDED")
    assert not e4s._NON_COMPUTING_RE.search("Software Test Engineer Placement")


# ─── StudentJob cards ───────────────────────────────────────────────────────

_SJ_FIXTURE = """
<a href="/vacancies/2971548-junior-software-developer-london?ref=1">
<div class="card__body job-opening__item">
<span>Junior Software Developer</span>
<img title="Acme Systems" src="x.png">
<span>London</span><span>£27,000 Per Year</span>
</div></a>
"""


def test_studentjob_card_reads_company_from_logo_title():
    cards = studentjob.parse_cards(_SJ_FIXTURE)
    assert len(cards) == 1
    card = cards[0]
    assert card["role"] == "Junior Software Developer"
    assert card["company"] == "Acme Systems"
    assert card["location"] == "London"
    assert card["salary"] == "£27,000 Per Year"
    assert card["url"].startswith("https://www.studentjob.co.uk/vacancies/2971548")


def test_studentjob_rejects_the_gig_spam():
    assert studentjob._NON_COMPUTING_RE.search("Get paid for your own opinion")
    assert studentjob._NON_COMPUTING_RE.search("Online Survey Taker")
    assert not studentjob._NON_COMPUTING_RE.search("Software Engineering Intern")


# ─── Personio XML feed ──────────────────────────────────────────────────────

_PERSONIO_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs><position>
<id>2670190</id>
<office>London, UK</office>
<department>IC Design</department>
<name><![CDATA[Analog IC Design Intern]]></name>
</position></workzag-jobs>
"""


def test_personio_positions_parse_with_cdata_names():
    positions = personio.parse_positions(_PERSONIO_FIXTURE)
    assert len(positions) == 1
    pos = positions[0]
    assert pos["name"] == "Analog IC Design Intern"
    assert pos["office"] == "London, UK"
    assert pos["department"] == "IC Design"
    assert pos["id"] == "2670190"
