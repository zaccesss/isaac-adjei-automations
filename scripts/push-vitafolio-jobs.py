"""Send the employer-direct student roles from the latest scrape to the Vitafolio Jobs page.

Only rows from employers' own hiring systems are sent: third-party job boards are scraped for this
tracker alone and their terms do not allow republishing. A row must be UK based, freshly stamped by
a scrape and still answer at its link. Vitafolio classifies every listing again on arrival, so the
type sent here is never trusted on its own.

Run after both scrape jobs. Without VITAFOLIO_JOBS_URL and VITAFOLIO_JOBS_TOKEN it does nothing.
VITAFOLIO_DRY_RUN=1 prints what would be sent and sends nothing.
"""
import html
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.locations import is_uk  # noqa: E402

# the hiring systems whose public job APIs may be shown elsewhere with a link back to the employer.
# workday and oracle careers sites forbid automated extraction in their terms; smartrecruiters, workable,
# eightfold, jibe and the big-company careers sites have no clear permission, so none of them is sent
EMPLOYER_SOURCES = {"Greenhouse", "Lever", "Ashby", "Recruitee", "Personio"}

# a row the scraper has not stamped this recently has dropped off its board
FRESH_DAYS = 2
BATCH = 500

def _plain(text: str) -> str:
    text = html.unescape(html.unescape(text or ""))
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


# Greenhouse's own job page hosts, matched exactly so a look-alike such as evilgreenhouse.io never counts
GREENHOUSE_HOSTS = {
    "boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.eu.greenhouse.io",
}


def board_of(url: str):
    """(board, slug, job id) for hiring systems whose public API returns the advert, else None."""
    parts = urlparse(url or "")
    host, path = parts.netloc.lower(), [p for p in parts.path.split("/") if p]
    if host in GREENHOUSE_HOSTS and len(path) >= 3 and path[-2] == "jobs":
        return ("greenhouse", path[0], path[-1])
    if host == "jobs.lever.co" and len(path) >= 2:
        return ("lever", path[0], path[1])
    if host == "jobs.ashbyhq.com" and len(path) >= 2:
        return ("ashby", path[0], path[1])
    return None


def fetch_description(session, url: str):
    """The advert text from the employer's own public job API, an empty string when there is none,
    or None when the employer has marked the job as unlisted and it must not be shown anywhere."""
    found = board_of(url)
    if not found:
        return ""
    board, slug, job_id = found
    try:
        if board == "greenhouse":
            resp = session.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}", timeout=10)
            return _plain(resp.json().get("content", "")) if resp.ok else ""
        if board == "lever":
            resp = session.get(f"https://api.lever.co/v0/postings/{slug}/{job_id}", timeout=10)
            if not resp.ok:
                return ""
            data = resp.json()
            lists = "\n\n".join(f"{x.get('text', '')}\n{_plain(x.get('content', ''))}" for x in data.get("lists", []))
            return "\n\n".join(p for p in (data.get("descriptionPlain", ""), lists, data.get("additionalPlain", "")) if p).strip()
        if board == "ashby":
            resp = session.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=15)
            if not resp.ok:
                return ""
            for job in resp.json().get("jobs", []):
                if job.get("id") == job_id or str(job.get("jobUrl", "")).rstrip("/").endswith(job_id):
                    if job.get("isListed") is False:
                        return None
                    return (job.get("descriptionPlain") or _plain(job.get("descriptionHtml", ""))).strip()
    except Exception:
        return ""
    return ""


def select_rows(rows, now=None):
    """The rows worth sending: student roles from employer sources, fresh, UK, with a link."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=FRESH_DAYS)
    picked, seen = [], set()
    for r in rows:
        url = (r.get("url") or "").strip()
        stamped = r.get("last_scraped_at")
        if (
            r.get("source") not in EMPLOYER_SOURCES
            or not url.startswith("https://")
            or not (r.get("role") or "").strip()
            or not is_uk(r.get("location") or "")
            or not stamped
            or datetime.fromisoformat(str(stamped).replace("Z", "+00:00")) < cutoff
            or url in seen
        ):
            continue
        seen.add(url)
        picked.append(r)
    return picked


def to_listing(r, description=""):
    return {
        "title": r["role"].strip(),
        "company": (r.get("company") or "").strip(),
        "url": r["url"].strip(),
        "location": (r.get("location") or "").strip() or None,
        "board": r.get("source"),
        "deadline": r.get("deadline") or None,
        "opened": r.get("opening_date") or None,
        "description": description or None,
        "category": r.get("category") or None,
    }


def main():
    url = os.environ.get("VITAFOLIO_JOBS_URL", "").strip()
    token = os.environ.get("VITAFOLIO_JOBS_TOKEN", "").strip()
    dry = os.environ.get("VITAFOLIO_DRY_RUN", "").strip() == "1"
    if not dry and (not url or not token):
        print("Vitafolio feed not configured; nothing sent.")
        return

    from supabase import create_client
    from scraper.http import SESSION, is_url_alive

    db = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip())
    rows = []
    for start in range(0, 200_000, 1000):
        page = db.table("applications").select(
            "company,role,type,source,location,deadline,opening_date,url,last_scraped_at,category"
        ).eq("status", "scraped").eq("archived", False).neq("type", "Full-time Job").in_("source", sorted(EMPLOYER_SOURCES)).range(start, start + 999).execute().data or []
        rows.extend(page)
        if len(page) < 1000:
            break

    picked = select_rows(rows)
    with ThreadPoolExecutor(max_workers=12) as pool:
        alive = list(pool.map(lambda r: is_url_alive(r["url"]), picked))
    picked = [r for r, ok in zip(picked, alive) if ok]
    with ThreadPoolExecutor(max_workers=8) as pool:
        descriptions = list(pool.map(lambda r: fetch_description(SESSION, r["url"]), picked))
    listings = [to_listing(r, d) for r, d in zip(picked, descriptions) if d is not None]
    print(f"{len(rows)} employer rows, {len(listings)} fresh UK listings with live links, "
          f"{sum(1 for d in descriptions if d)} with an advert, {sum(1 for d in descriptions if d is None)} unlisted")

    if dry:
        for item in listings[:40]:
            print(f"  {item['board']:<18} {item['company'][:28]:<28} {item['title'][:70]}")
        return

    for i in range(0, len(listings), BATCH):
        resp = SESSION.post(url, json={"jobs": listings[i:i + BATCH]}, timeout=60,
                            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        resp.raise_for_status()
        print(resp.json())


if __name__ == "__main__":
    main()
