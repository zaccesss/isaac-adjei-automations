"""Source: Oracle Recruiting Cloud (Candidate Experience API).

Several large employers run their careers site on Oracle Recruiting Cloud, whose
public REST API returns jobs with a plain request - no browser - once the expand
parameter is supplied. Without expand the keyword search answers a count but an
empty list, which is the trap that makes this look unscrapeable at first.

Each tenant is (host, site, display_name). JPMorgan and Texas Instruments are both
here; more Oracle employers can join as I verify each host and site number. I keep
the UK early-careers tech roles, filtered by their location.
"""
from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, resolve_type
from ..http import HEADERS, SESSION
from ..budget import over_budget
from ..stats import record_stat

# (host, site number, display name)
ORACLE_COMPANIES = [
    ("jpmc.fa.oraclecloud.com",     "CX_1001", "JPMorgan Chase"),
    ("edbz.fa.us2.oraclecloud.com", "CX",      "Texas Instruments"),
]

_KEYWORDS = ("intern", "graduate", "apprentice", "placement")


def scrape_oracle(ctx, host: str, site: str, company_name: str) -> int:
    """Read one Oracle tenant's jobs API, keeping UK tech early-careers roles."""
    api = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    job_base = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job"
    count = 0
    seen: set[str] = set()
    for keyword in _KEYWORDS:
        for offset in range(0, 120, 10):
            finder = (
                f'findReqs;siteNumber={site},keyword="{keyword}",'
                f"limit=10,offset={offset},sortBy=POSTING_DATES_DESC"
            )
            try:
                resp = SESSION.get(
                    api,
                    params={
                        "onlyData": "true",
                        "expand": "requisitionList.workLocation",
                        "finder": finder,
                    },
                    headers={**HEADERS, "Accept": "application/json"},
                    timeout=20,
                )
                if resp.status_code != 200:
                    break
                items = resp.json().get("items", [])
                reqs = items[0].get("requisitionList", []) if items else []
            except Exception as e:
                print(f"  {company_name} {keyword} offset={offset}: {e}")
                break
            if not reqs:
                break
            for job in reqs:
                role = (job.get("Title") or "").strip()
                location = (job.get("PrimaryLocation") or "").strip()
                jid = job.get("Id") or ""
                if not role or not jid or "United Kingdom" not in location:
                    continue
                if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                    continue
                if not _has_tech_keyword(role.lower()):
                    continue
                url = f"{job_base}/{jid}"
                if url in seen:
                    continue
                seen.add(url)
                if insert_job(ctx, {
                    "company":  company_name,
                    "role":     role,
                    "type":     resolve_type(role, fallback="Internship"),
                    "url":      url,
                    "location": location,
                    "source":   "Oracle",
                }):
                    count += 1
    return count


def run(ctx) -> int:
    print("\n--- Oracle Recruiting Cloud ---")
    total = 0
    for host, site, name in ORACLE_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Oracle companies")
            break
        try:
            n = scrape_oracle(ctx, host, site, name)
            if n:
                print(f"  {name}: {n} new")
            total += n
        except Exception as e:
            print(f"  Error {name} Oracle: {e}")
    record_stat(ctx, "Oracle", total)
    return total
