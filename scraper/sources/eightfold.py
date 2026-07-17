"""Source: Eightfold (public jobs API).

Eightfold is an ATS platform many large employers use, including STMicroelectronics.
Its careers widget is backed by a public JSON endpoint that needs no browser and no
key: /api/apply/v2/jobs?domain={domain}&start={n}&num={size}. Each position carries
its canonicalPositionUrl - the specific role page - along with the location and the
full description, so I read it the same way as the other ATS families.
"""
import time

from ..data.companies import EIGHTFOLD_COMPANIES
from ..db import insert_job
from ..detect import _strip_html, detect_cover_letter_required, detect_sponsors_visa
from ..filters import resolve_type, is_relevant, is_relevant_job
from ..http import HEADERS, SESSION
from ..budget import over_budget
from ..stats import record_stat


def scrape_eightfold(ctx, tenant: str, domain: str, company_name: str) -> int:
    """Page an Eightfold tenant's public jobs API, filtering to UK tech roles."""
    base = f"https://{tenant}.eightfold.ai/api/apply/v2/jobs"
    count = 0
    start = 0
    total = None
    while total is None or start < total:
        try:
            # The API scopes to the UK for me: these are global employers whose
            # worldwide fabs would otherwise flood the Jobs tab, and the UK design
            # centres are the only ones I can take a placement at.
            resp = SESSION.get(
                base,
                params={
                    "domain": domain,
                    "start": start,
                    "num": 20,
                    "location": "United Kingdom",
                    "sort_by": "relevance",
                },
                headers={**HEADERS, "Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Eightfold {company_name}: HTTP {resp.status_code}")
                break
            data = resp.json()
            if total is None:
                total = data.get("count", 0)
            positions = data.get("positions", [])
            if not positions:
                break
            for pos in positions:
                title = pos.get("name", "")
                location = pos.get("location", "")
                url = pos.get("canonicalPositionUrl", "")
                description = _strip_html(pos.get("job_description", ""))
                # Eightfold tags a department; I pass it alongside the title so a
                # graduate-pipeline department still reads as a student role.
                depts = [pos.get("department", "")] if pos.get("department") else None
                if is_relevant(title, company_name, location, depts):
                    if insert_job(ctx, {
                        "company":               company_name,
                        "role":                  title,
                        "type":                  resolve_type(title),
                        "url":                   url,
                        "location":              location,
                        "source":                "Eightfold",
                        "sponsors_visa":         detect_sponsors_visa(description),
                        "cover_letter_required": detect_cover_letter_required(description),
                        "description":           description,
                    }):
                        count += 1
                elif is_relevant_job(title, company_name, location):
                    if insert_job(ctx, {
                        "company":               company_name,
                        "role":                  title,
                        "type":                  "Full-time Job",
                        "url":                   url,
                        "location":              location,
                        "source":                "Eightfold",
                        "sponsors_visa":         detect_sponsors_visa(description),
                        "cover_letter_required": detect_cover_letter_required(description),
                        "description":           description,
                    }):
                        count += 1
            start += len(positions)
            time.sleep(0.4)
        except Exception as e:
            print(f"  Error Eightfold {company_name} start={start}: {e}")
            break
    print(f"  Added {count} from {company_name} (Eightfold)")
    return count


def run(ctx) -> int:
    print("\n--- Eightfold ---")
    total = 0
    for tenant, domain, name in EIGHTFOLD_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Eightfold companies")
            break
        try:
            total += scrape_eightfold(ctx, tenant, domain, name)
        except Exception as e:
            print(f"  Error {name} Eightfold: {e}")
    record_stat(ctx, "Eightfold", total)
    return total
