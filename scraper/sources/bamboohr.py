"""Source: BambooHR (public careers list).

Small UK silicon firms run their careers pages on BambooHR, whose careers list is
a keyless JSON endpoint: every opening's id, title, department and location. The
role's own page is /careers/{id} on the same host. Added November 2026 for the
UKESF partner companies; every employer here is capped and guarded as a newer source.
"""
import time

from ..budget import over_budget
from ..db import insert_job
from ..filters import passes_new_source_guard, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat

# (subdomain, display_name), each checked live November 2026. Cosmic Semiconductor
# still posts under its former IPTest name.
BAMBOOHR_COMPANIES = [
    ("codasip", "Codasip"),
    ("ensilica", "EnSilica"),
    ("iptest", "Cosmic Semiconductor"),
]


def _location(opening: dict) -> str:
    loc = opening.get("location") or {}
    ats = opening.get("atsLocation") or {}
    parts = [loc.get("city"), loc.get("state"), ats.get("country")]
    text = ", ".join(p for p in parts if p)
    if not text and opening.get("isRemote"):
        text = "Remote"
    return text


def parse_openings(payload: dict, subdomain: str) -> list[dict]:
    """The openings in one careers list as plain dicts: title, url, location and department."""
    jobs = []
    for opening in payload.get("result") or []:
        jid = opening.get("id")
        jobs.append({
            "title":    (opening.get("jobOpeningName") or "").strip(),
            "url":      f"https://{subdomain}.bamboohr.com/careers/{jid}" if jid else "",
            "location": _location(opening),
            "depts":    [opening["departmentLabel"]] if opening.get("departmentLabel") else None,
        })
    return jobs


def scrape_bamboohr(ctx, subdomain: str, company_name: str) -> int:
    try:
        resp = SESSION.get(
            f"https://{subdomain}.bamboohr.com/careers/list",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  BambooHR {company_name}: HTTP {resp.status_code}")
            return 0
        jobs = parse_openings(resp.json(), subdomain)
    except Exception as e:
        print(f"  Error BambooHR {company_name}: {e}")
        return 0
    count = 0
    for job in jobs:
        if not passes_new_source_guard(job["title"], company_name, job["location"], None, job["depts"]):
            continue
        if insert_job(ctx, {
            "company":  company_name,
            "role":     job["title"],
            "type":     resolve_type(job["title"]),
            "url":      job["url"],
            "location": job["location"],
            "source":   "BambooHR",
            "cap_key":  company_name,
        }):
            count += 1
    if count:
        print(f"  Added {count} from {company_name} (BambooHR)")
    return count


def run(ctx) -> int:
    print("\n--- BambooHR ---")
    total = 0
    for subdomain, name in BAMBOOHR_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining BambooHR companies")
            break
        total += scrape_bamboohr(ctx, subdomain, name)
        time.sleep(0.5)
    record_stat(ctx, "BambooHR", total)
    return total
