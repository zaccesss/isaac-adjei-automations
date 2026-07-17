"""One-off experiment: can Scrapling's Cloudflare solver reach the blocked boards
from a GitHub Actions runner?

curl_cffi clears Cloudflare's TLS-fingerprint layer but not its IP-reputation
layer, and GitHub's shared runner IPs are flagged, so Bright Network and Milkround
returned 403 in CI while working from a home IP. Scrapling's StealthyFetcher runs a
real Camoufox browser and solves the JS or Turnstile challenge; if the CI block is
that challenge layer rather than a hard IP ban, this reaches the boards with no
proxy and no external VM. This script just reports the outcome so I can decide
whether to wire Scrapling into the scraper - it writes nothing to the database.
"""
import re
import sys

TARGETS = [
    ("Gradcracker", "https://www.gradcracker.com/search/computing-technology/internships-work-placements", r"/work-placement-internship/\d+/"),
    ("Bright Network", "https://www.brightnetwork.co.uk/internships/", r"/graduate-jobs/[^/]+/[^/\"?]+"),
    ("Milkround", "https://www.milkround.com/jobs/graduate-technology", r"totaljobs\.com/job/"),
]


def main() -> None:
    try:
        from scrapling.fetchers import StealthyFetcher
    except Exception as e:
        print(f"scrapling import failed: {e}")
        sys.exit(1)

    for name, url, job_re in TARGETS:
        try:
            page = StealthyFetcher.fetch(
                url,
                headless=True,
                solve_cloudflare=True,
                network_idle=True,
                timeout=90000,
            )
            html = page.html_content or ""
            status = page.status
            job_links = len(set(re.findall(job_re, html)))
            verdict = "REACHED" if job_links > 0 else ("got page, no jobs" if status == 200 else "blocked")
            print(f"[{name}] status={status} html={len(html)//1000}k job_links={job_links} -> {verdict}")
        except Exception as e:
            print(f"[{name}] ERROR: {e}")


if __name__ == "__main__":
    main()
