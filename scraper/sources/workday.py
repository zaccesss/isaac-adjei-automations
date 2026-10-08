"""Source: workday."""

import time
from ..data.companies import PRIORITY_COMPANIES
from ..db import insert_job
from ..filters import _has_tech_keyword, is_relevant, is_relevant_job, is_student_role, resolve_type
from ..http import HEADERS
from ..locations import MULTI_LOCATION_RE, is_location_ok
from ..budget import over_budget
from ..stats import record_stat
from ..http import SESSION

# ─── WORKDAY API (NVIDIA, Intel and other Workday-hosted companies) ─────────

# confirmed Workday configurations: (subdomain, wdnum, tenant, site_id, display_name)
# validated against live API - POST to /wday/cxs/{tenant}/{site_id}/jobs.
# ARM, Goldman, JPMorgan, Qualcomm, BAE, Rolls-Royce use Workday but require
# session cookies or proprietary auth - scrape via The Trackr (Playwright) instead.
WORKDAY_COMPANIES = [
    ("nvidia", "5", "nvidia", "NVIDIAExternalCareerSite", "NVIDIA"),
    ("intel",  "1", "intel",  "External",                 "Intel"),
    ("ms",     "5", "ms",     "External",                 "Morgan Stanley"),
    # semiconductor majors, confirmed live July 2026 - the embedded and hardware
    # placements in scope live on exactly these boards.
    ("analogdevices", "1", "analogdevices", "External",       "Analog Devices"),
    ("micron",        "1", "micron",        "External",       "Micron"),
    ("nxp",           "3", "nxp",           "careers",        "NXP"),
    ("marvell",       "1", "marvell",       "MarvellCareers", "Marvell"),
    # confirmed live July 2026. Broadcom answered 101 postings to an intern
    # search; HPE also covers Juniper since the acquisition. Qualcomm stays out:
    # its CXS endpoint returns 422 to every plain payload, so it wants the
    # front-end's session tokens like the other auth-gated tenants above.
    ("broadcom", "1", "broadcom", "External_Career", "Broadcom"),
    ("hpe",      "5", "hpe",      "ACJobSite",       "HPE"),
    # added October 2026, each checked live against its job board
    ("barclays", "3", "barclays", "External_Career_Site_Barclays", "Barclays"),
    ("rbs", "3", "rbs", "rbs", "NatWest Group"),
    ("citi", "5", "citi", "2", "Citi"),
    ("lseg", "3", "lseg", "Careers", "LSEG"),
    ("boeing", "1", "boeing", "External_Careers", "Boeing"),
    ("hp", "5", "hp", "ExternalCareerSite", "HP"),
    ("gevernova", "5", "gevernova", "Vernova_ExternalSite", "GE Vernova"),
    ("matthey", "3", "matthey", "Ext_Career_Site", "Johnson Matthey"),
    ("gsk", "5", "gsk", "gskcareers", "GSK"),
    ("shell", "3", "shell", "shellcareers", "Shell"),
    ("cisco", "5", "cisco", "Cisco_Careers", "Cisco"),
    ("visa", "5", "visa", "Visa_Early_Careers", "Visa"),
    ("spgi", "5", "spgi", "Spgi_Careers", "S&P Global"),
    ("mmc", "1", "mmc", "mmc", "Marsh McLennan"),
    ("wellington", "5", "wellington", "External", "Wellington Management"),
    ("pimco", "1", "pimco", "Pimco-Careers", "PIMCO"),
    ("hl", "1", "hl", "Campus", "Houlihan Lokey"),
    ("ag", "3", "ag", "Airbus", "Airbus"),
    ("halma", "3", "halma", "halma", "Halma"),
    ("relx", "3", "relx", "Relx", "RELX"),
    ("leonardocompany", "3", "leonardocompany", "LeonardoCareerSite", "Leonardo"),
    ("lbg", "3", "lbg", "LBG_Careers", "Lloyds Banking Group"),
    ("darktrace", "3", "darktrace", "DarktaceExternal", "Darktrace"),
    ("dyson", "3", "dyson", "Dyson_Careers", "Dyson"),
    ("cadence", "1", "cadence", "External_Careers", "Cadence"),
    ("latticesemi", "5", "latticesemi", "latticesemiconductorscareers", "Lattice Semiconductor"),
    ("renishaw", "3", "renishaw", "Renishaw", "Renishaw"),
    ("crowdstrike", "5", "crowdstrike", "crowdstrikecareers", "CrowdStrike"),
    ("paloaltonetworks", "5", "paloaltonetworks", "panwexternalcareers", "Palo Alto Networks"),
    ("arcticwolf", "1", "arcticwolf", "External", "Arctic Wolf"),
    ("kainos", "3", "kainos", "kainos", "Kainos"),
    ("kyndryl", "5", "kyndryl", "KyndrylEarlyCareers", "Kyndryl"),
    ("accenture", "103", "accenture", "AccentureCareers", "Accenture"),
    ("statestreet", "1", "statestreet", "Global", "State Street"),
    ("santander", "3", "santander", "santandercareers", "Santander"),
    ("ig", "103", "ig", "EXT_IG", "IG Group"),
    ("cmcmarkets", "3", "cmcmarkets", "CMC_Markets_Careers", "CMC Markets"),
    ("nasdaq", "1", "nasdaq", "Global_External_Site", "Nasdaq"),
    ("fis", "5", "fis", "SearchJobs", "FIS"),
    ("mastercard", "1", "mastercard", "CorporateCareers", "Mastercard"),
    ("thomsonreuters", "5", "thomsonreuters", "External_Career_Site", "Thomson Reuters"),
    ("aveva", "3", "aveva", "AVEVA_careers", "AVEVA"),
    ("sonyglobal", "1", "sonyglobal", "sonyglobalcareers", "Sony"),
    ("moog", "5", "moog", "Moog_External_Career_Site", "Moog"),
    ("aviva", "1", "aviva", "External", "Aviva"),
]


def _posting_locations(base: str, external_path: str) -> str:
    """Every place a Workday posting names, joined with semicolons; empty when unknown."""
    if not external_path:
        return ""
    try:
        resp = SESSION.get(f"{base}{external_path}", headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return ""
        info = resp.json().get("jobPostingInfo", {})
        places = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
        return "; ".join(p for p in places if p)
    except Exception:
        return ""


def scrape_workday(
    ctx, subdomain: str, wdnum: str, tenant: str, site_id: str,
    company_name: str
) -> int:
    """Scrape a Workday-hosted career site via their internal CXS API.

    Workday requires a POST request with JSON body - a plain GET returns 404.
    I page through all results and filter by UK location after retrieval.
    """
    url = (
        f"https://{subdomain}.wd{wdnum}.myworkdayjobs.com"
        f"/wday/cxs/{tenant}/{site_id}/jobs"
    )
    print(f"\nScraping {company_name} Workday...")
    count = 0
    offset = 0
    total = None
    # a few large employers answer a search for "intern" with thousands of loose matches, so one
    # employer may read at most this many results before the run moves on
    max_results = 200
    while (total is None or offset < total) and offset < max_results:
        try:
            resp = SESSION.post(
                url,
                json={"limit": 20, "offset": offset, "searchText": "intern"},
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  {company_name} Workday: HTTP {resp.status_code}")
                break
            data = resp.json()
            if total is None:
                total = data.get("total", 0)
            jobs = data.get("jobPostings", [])
            if not jobs:
                break
            for job in jobs:
                title = job.get("title", "")
                # Workday location is in 'locationsText' or the first bulletField.
                location_text = job.get("locationsText", "") or ""
                if not location_text:
                    for bf in job.get("bulletFields", []):
                        if bf:
                            location_text = bf
                            break
                # a multi-site posting only says "2 Locations"; its own detail record names them,
                # fetched only for titles that would be kept so a run stays within its budget
                if MULTI_LOCATION_RE.match(location_text) and (
                    is_student_role(title) or _has_tech_keyword(title.lower())
                ):
                    location_text = _posting_locations(url[:-len("/jobs")], job.get("externalPath", "")) or location_text
                # pre-filter non-UK roles to avoid HEAD-checking hundreds of
                # US job URLs. is_relevant does a second check inside.
                is_priority = any(p in company_name.lower() for p in PRIORITY_COMPANIES)
                if location_text and not is_location_ok(location_text, is_priority) and not is_student_role(title):
                    continue
                ext_url = job.get("externalPath", "")
                job_url = (
                    f"https://{subdomain}.wd{wdnum}.myworkdayjobs.com"
                    f"/en-US/{site_id}{ext_url}"  # externalPath already starts with /job/
                ) if ext_url else ""
                if is_relevant(title, company_name, location_text):
                    if insert_job(ctx, {
                        "company":  company_name,
                        "role":     title,
                        "type":     resolve_type(title),
                        "url":      job_url,
                        "location": location_text,
                        "source":   "Workday",
                    }):
                        count += 1
                elif is_relevant_job(title, company_name, location_text):
                    if insert_job(ctx, {
                        "company":  company_name,
                        "role":     title,
                        "type":     "Full-time Job",
                        "url":      job_url,
                        "location": location_text,
                        "source":   "Workday",
                    }):
                        count += 1
            offset += len(jobs)
            time.sleep(0.5)
            if len(jobs) < 20:
                break
        except Exception as e:
            print(f"  Error {company_name} Workday offset={offset}: {e}")
            break
    print(f"  Added {count} from {company_name} Workday")
    return count


def run(ctx) -> int:
    print("\n--- Workday (NVIDIA / Intel / Morgan Stanley) ---")
    total = 0
    for subdomain, wdnum, tenant, site_id, name in WORKDAY_COMPANIES:
        if over_budget(ctx):
            break
        try:
            total += scrape_workday(ctx, subdomain, wdnum, tenant, site_id, name)
        except Exception as e:
            print(f"  Error {name} Workday: {e}")
    record_stat(ctx, "Workday", total)
    return total
