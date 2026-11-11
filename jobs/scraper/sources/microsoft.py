"""Source: microsoft."""

import time
from ..db import insert_job
from ..filters import resolve_type, is_relevant
from ..http import HEADERS
from ..stats import record_stat
from ..http import SESSION

# ─── MICROSOFT CAREERS ────────────────────────────────────────────────────────

def scrape_microsoft(ctx) -> int:
    """Scrape Microsoft UK internships from their careers portal."""
    print("\nScraping Microsoft Careers (UK)...")
    count = 0
    page = 1
    while page <= 10:
        try:
            resp = SESSION.get(
                "https://jobs.careers.microsoft.com/api/jobs/search",
                params={
                    "q": "intern",
                    "lc": "United Kingdom",
                    "l": "en_us",
                    "pg": str(page),
                    "pgSz": "20",
                    "o": "Relevance",
                    "flt": "true",
                },
                headers={
                    **HEADERS,
                    "Referer": "https://jobs.careers.microsoft.com/",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"  Microsoft: HTTP {resp.status_code}")
                break
            data = resp.json()
            jobs_list = (
                data.get("operationResult", {})
                    .get("result", {})
                    .get("jobs", [])
            )
            if not jobs_list:
                break
            for job in jobs_list:
                title = job.get("title", "")
                props = job.get("properties", {})
                location = props.get("primaryWorkLocation", "")
                jid = job.get("jobId", "")
                job_url = (
                    f"https://jobs.careers.microsoft.com/global/en/job/{jid}"
                    if jid else ""
                )
                if not is_relevant(title, "Microsoft", location):
                    continue
                if insert_job(ctx, {
                    "company":  "Microsoft",
                    "role":     title,
                    "type":     resolve_type(title),
                    "url":      job_url,
                    "location": location,
                    "source":   "Microsoft Careers",
                }):
                    count += 1
            if len(jobs_list) < 20:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error Microsoft p{page}: {e}")
            break
    print(f"  Added {count} from Microsoft Careers")
    return count


def run(ctx) -> int:
    print("\n--- Microsoft Careers ---")
    try:
        n = scrape_microsoft(ctx)
        record_stat(ctx, "Microsoft Careers", n)
        return n
    except Exception as e:
        print(f"  Error Microsoft: {e}")
        record_stat(ctx, "Microsoft Careers", 0, str(e))
        return 0
