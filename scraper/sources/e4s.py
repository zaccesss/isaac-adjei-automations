"""Source: E4S - Employment 4 Students (embedded Apollo state).

E4S is a Next.js app whose category pages ship their jobs inside the page's
embedded Apollo GraphQL cache: each Job entity carries the title, the
organisation, the posting's own URL, an ISO expiration that becomes the
deadline and the occupational-field labels I pass to the classifier as
departments. The board is mostly seasonal part-time work, so I read only the
IT and engineering categories and let the shared filters keep the genuine
student tech roles.
"""
import json
import re

from ..db import insert_job
from ..filters import _NON_TECH_ROLE_RE, _SENIOR_ROLE_RE, _has_tech_keyword, infer_type
from ..http import HEADERS, SESSION
from ..locations import normalize_location
from ..stats import record_stat

BASE = "https://www.e4s.co.uk"

LISTINGS = ["/jobs/it", "/jobs/engineer"]

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
# E4S prefixes pre-registration listings the same way RateMyPlacement does.
_PREREG_PREFIX_RE = re.compile(r"^\s*register\s+your\s+interest\s*[-:]\s*", re.I)
# The survey and gig spam this board floods its categories with. "test" is a
# whole-word tech keyword (QA), so "paid test user" would otherwise pass.
_NON_COMPUTING_RE = re.compile(
    r"\b(test users?|game testers?|your own opinion|survey|panelist|mystery shop|"
    r"delivery|driver|warehouse|barista|waiter|bartend|retail|nanny|babysit|"
    r"care assistant|promoter|charity|fundrais|tutor)\b",
    re.I,
)


def parse_jobs(page_html: str) -> list[dict]:
    """Return the jobs in one E4S category page's Apollo cache as plain dicts."""
    m = _NEXT_DATA_RE.search(page_html)
    if not m:
        return []
    try:
        state = json.loads(m.group(1))["props"]["pageProps"]["__APOLLO_STATE__"]
    except Exception:
        return []
    jobs = []
    for key, entity in state.items():
        if not key.startswith("Job:") or not isinstance(entity, dict):
            continue
        title = _PREREG_PREFIX_RE.sub("", entity.get("title") or "").strip()
        if not title:
            continue
        org = ""
        ref = entity.get("organizationProfile")
        if isinstance(ref, dict):
            profile = state.get(ref.get("__ref", ""), ref)
            org = (profile or {}).get("name", "")
        if not org:
            org = (entity.get("organization") or "").replace("-", " ").title()
        url = entity.get("absoluteUrl") or ""
        if not url:
            path = (entity.get("url") or {}).get("path") or entity.get("urlNoPrefix") or ""
            url = f"{BASE}{path}" if path else ""
        expiration = entity.get("expiration") or ""
        fields = [
            t.get("label", "")
            for t in entity.get("occupationalField") or []
            if isinstance(t, dict)
        ]
        jobs.append({
            "role":     title,
            "company":  org,
            "location": ", ".join(entity.get("address") or []),
            "url":      url,
            "deadline": expiration[:10] if len(expiration) >= 10 else None,
            "depts":    fields,
        })
    return jobs


def scrape_e4s(ctx) -> int:
    """Page the IT and engineering categories until a page adds nothing."""
    print("\nScraping E4S...")
    total = 0
    for path in LISTINGS:
        for page in range(1, 6):
            try:
                resp = SESSION.get(
                    f"{BASE}{path}", params={"page": page}, headers=HEADERS, timeout=20
                )
                if resp.status_code != 200:
                    break
                jobs = parse_jobs(resp.text)
            except Exception as e:
                print(f"  Error E4S {path} page={page}: {e}")
                break
            if not jobs:
                break
            added = 0
            for job in jobs:
                role = job["role"]
                if not job["company"] or not job["url"]:
                    continue
                if _SENIOR_ROLE_RE.search(role) or _NON_TECH_ROLE_RE.search(role):
                    continue
                if _NON_COMPUTING_RE.search(role):
                    continue
                if not _has_tech_keyword(role.lower()):
                    continue
                if insert_job(ctx, {
                    "company":  job["company"],
                    "role":     role,
                    "type":     infer_type(role, default="Internship"),
                    "url":      job["url"],
                    "location": normalize_location(job["location"]),
                    "deadline": job["deadline"],
                    "source":   "E4S",
                }):
                    added += 1
            total += added
            if added == 0:
                break
    print(f"  E4S total: {total} new")
    return total


def run(ctx) -> int:
    print("\n--- E4S ---")
    try:
        n = scrape_e4s(ctx)
        record_stat(ctx, "E4S", n)
        return n
    except Exception as e:
        print(f"  Error E4S: {e}")
        record_stat(ctx, "E4S", 0, str(e))
        return 0
