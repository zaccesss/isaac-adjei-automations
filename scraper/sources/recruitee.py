"""Source: Recruitee (public offers API).

Recruitee is another startup ATS with a keyless JSON endpoint: one GET per
company returns every published offer with its title, city, country and the
offer's own careers page URL. The seeded list leans UK studios and product
companies; the shared classifier keeps only student tech roles, with full-time
roles surviving only through the priority-company path like every other source.
"""
import time

from ..budget import over_budget
from ..data.companies import RECRUITEE_COMPANIES
from ..db import insert_job
from ..detect import _strip_html, detect_cover_letter_required, detect_sponsors_visa
from ..filters import is_relevant, is_relevant_job, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat


def scrape_recruitee(ctx, slug: str, company_name: str) -> int:
    """Read one Recruitee tenant's offers and keep the UK student tech roles."""
    url = f"https://{slug}.recruitee.com/api/offers/"
    count = 0
    try:
        resp = SESSION.get(
            url, headers={**HEADERS, "Accept": "application/json"}, timeout=15
        )
        if resp.status_code != 200:
            print(f"  Recruitee {company_name}: HTTP {resp.status_code}")
            return 0
        offers = resp.json().get("offers", [])
    except Exception as e:
        print(f"  Error Recruitee {company_name}: {e}")
        return 0
    for offer in offers:
        title = offer.get("title", "")
        location = offer.get("location", "") or ", ".join(
            p for p in [offer.get("city"), offer.get("country")] if p
        )
        job_url = offer.get("careers_url", "")
        depts = [offer.get("department", "")] if offer.get("department") else None
        description = _strip_html(offer.get("description", ""))
        extra = {
            "sponsors_visa":         detect_sponsors_visa(description),
            "cover_letter_required": detect_cover_letter_required(description),
            "description":           description,
        }
        if is_relevant(title, company_name, location, depts):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     resolve_type(title),
                "url":      job_url,
                "location": location,
                "source":   "Recruitee",
                **extra,
            }):
                count += 1
        elif is_relevant_job(title, company_name, location):
            if insert_job(ctx, {
                "company":  company_name,
                "role":     title,
                "type":     "Full-time Job",
                "url":      job_url,
                "location": location,
                "source":   "Recruitee",
                **extra,
            }):
                count += 1
    if count:
        print(f"  Added {count} from {company_name} (Recruitee)")
    return count


def run(ctx) -> int:
    print("\n--- Recruitee ---")
    total = 0
    for slug, name in RECRUITEE_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining Recruitee companies")
            break
        total += scrape_recruitee(ctx, slug, name)
        time.sleep(0.3)
    record_stat(ctx, "Recruitee", total)
    return total
