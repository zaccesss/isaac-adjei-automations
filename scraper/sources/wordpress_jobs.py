"""Source: employers' own WordPress careers pages (REST API).

A few small UK electronics firms list vacancies as a WordPress post type, which
the site's public REST API returns as JSON: the title and the vacancy's own page.
These posts carry no location field, so each site's postings are filed under the
UK, the only country its careers page recruits for. Added November 2026 for the
UKESF partner companies; every employer here is capped and guarded as a newer source.
"""
import html
import time

from ..budget import over_budget
from ..db import insert_job
from ..filters import passes_new_source_guard, resolve_type
from ..http import HEADERS, SESSION
from ..stats import record_stat

# (site, post_type, display_name), each endpoint checked live November 2026.
# Blighter's robots.txt asks for a 10 second crawl delay, which one request a run respects.
WORDPRESS_COMPANIES = [
    ("https://www.blighter.com", "job", "Blighter"),
    ("https://www.cmlmicro.com", "career", "CML Micro"),
    ("https://www.viperinnovations.com", "vacancy", "Viper Innovations"),
    ("https://www.mktest.com", "job-listings", "MK Test Systems"),
]
_LOCATION = "United Kingdom"


def parse_posts(posts: list) -> list[dict]:
    """The posts as plain dicts: the decoded title and the post's own link."""
    jobs = []
    for post in posts or []:
        title = html.unescape(((post.get("title") or {}).get("rendered") or "")).strip()
        jobs.append({"title": " ".join(title.split()), "url": post.get("link") or ""})
    return jobs


def scrape_wordpress(ctx, site: str, post_type: str, company_name: str) -> int:
    try:
        resp = SESSION.get(
            f"{site}/wp-json/wp/v2/{post_type}",
            params={"per_page": 50},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"  WordPress {company_name}: HTTP {resp.status_code}")
            return 0
        jobs = parse_posts(resp.json())
    except Exception as e:
        print(f"  Error WordPress {company_name}: {e}")
        return 0
    count = 0
    for job in jobs:
        if not passes_new_source_guard(job["title"], company_name, _LOCATION):
            continue
        if insert_job(ctx, {
            "company":  company_name,
            "role":     job["title"],
            "type":     resolve_type(job["title"]),
            "url":      job["url"],
            "location": _LOCATION,
            "source":   "Company site",
            "cap_key":  company_name,
        }):
            count += 1
    if count:
        print(f"  Added {count} from {company_name} (WordPress)")
    return count


def run(ctx) -> int:
    print("\n--- Company WordPress careers pages ---")
    total = 0
    for site, post_type, name in WORDPRESS_COMPANIES:
        if over_budget(ctx):
            print("  [budget] skipping remaining WordPress careers pages")
            break
        total += scrape_wordpress(ctx, site, post_type, name)
        time.sleep(1)
    record_stat(ctx, "WordPress careers", total)
    return total
