"""Supabase access: dedupe keys, existing-row loading, the insert-or-refresh upsert and the freshness stamp."""

import os
import hashlib
from supabase import create_client, Client
from datetime import datetime, timezone
from .ai import _ai_fill
from .dates import CYCLE_CUTOFF, JOB_CUTOFF, is_date_relevant
from .filters import detect_category
from .http import is_url_alive
from .locations import normalize_location

# I read credentials from environment variables set by GitHub Actions secrets
# so nothing sensitive ever touches the repository.
SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()

# I create the client at module level so it is shared across all scraper
# functions rather than re-initialising a new connection for every company.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── DEDUPLICATION ──────────────────────────────────────────────────────────

def dedupe_key(company: str, role: str, url: str = "") -> str:
    # I prefer URL-based deduplication so the same job posting scraped from
    # two different sources is never inserted twice. I strip trailing slashes
    # because the same URL can appear with and without one.
    if url and url.startswith("http"):
        # I normalise both Greenhouse URL domains to the old format so rows
        # inserted before the domain change (boards.greenhouse.io) and rows
        # inserted after (job-boards.greenhouse.io) hash to the same key and
        # never trigger a 23505 unique constraint violation.
        url = url.replace("job-boards.greenhouse.io", "boards.greenhouse.io")
        raw = url.strip().rstrip("/")
    else:
        # I fall back to company+role when there is no URL. I lower-case and
        # strip both fields so "Google" and "google" hash identically.
        raw = f"{company.lower().strip()}|{role.lower().strip()}"
    # I use a truncated MD5 (16 hex chars) as the key - collision probability
    # is negligible for a few thousand rows and fits in a set comfortably.
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def load_existing_keys() -> set:
    # I load all existing keys at the start of each run so every insert check
    # is an O(1) set lookup rather than a DB query per row. On a fresh DB this
    # returns an empty set and everything gets inserted.
    try:
        res = supabase.table("applications").select(
            "company,role,url"
        ).execute()
        existing_keys = {
            dedupe_key(r["company"], r["role"], r.get("url") or "")
            for r in (res.data or [])
        }
        # Remember which URLs already exist so insert_job updates them in place rather than skipping.
        _existing_urls.update(r["url"] for r in (res.data or []) if r.get("url"))
        if not existing_keys:
            # I warn here because an empty result on a populated DB usually
            # means RLS is blocking the SELECT - the upsert below will still
            # prevent duplicates at the DB level so this is non-fatal.
            print("WARNING: 0 existing rows loaded - RLS may be blocking reads. Continuing with upsert deduplication.")
        return existing_keys
    except Exception as e:
        # I log and continue rather than crashing - the upsert strategy means
        # no duplicates are created even if this pre-load fails.
        print(f"Warning: could not load existing keys: {e}")
        return set()


# ─── INSERT ─────────────────────────────────────────────────────────────────

# I collect URLs seen this run so I can batch-refresh last_scraped_at at the
# end without overwriting user-set status, notes or other fields.
_seen_urls: set[str] = set()
# URLs already in the DB at load time, so insert_job knows whether to insert a new row or refresh the
# scraper-owned fields of an existing one (upsert-by-URL, never delete, never clobber user edits).
_existing_urls: set[str] = set()
# I collect newly inserted student jobs for the end-of-run Discord alert.
_new_jobs: list[dict] = []


# Columns the scraper owns and may overwrite on an existing row. Everything else (status, notes,
# starred, applied_date) is user-owned and is NEVER touched on an update, so a re-scrape refreshes
# stale data - including the CV / cover letter / written-answers facts now read from The Trackr -
# without clobbering my app edits.
SCRAPER_FIELDS = {
    "company", "role", "type", "location", "deadline", "opening_date",
    "salary_range", "work_mode", "source", "sponsors_visa", "category", "last_scraped_at",
    "last_year_opening", "housing_location", "cv_required", "cover_letter_required",
    "written_answers",
}


def _cover_letter_label(v):
    # Scrapers pass True/False/None (or occasionally a string); the app stores the text labels
    # "Yes"/"No"/"Optional", so normalise to that rather than a Python bool that becomes "true".
    if v is True:
        return "Yes"
    if v is False:
        return "No"
    if isinstance(v, str) and v.strip():
        return v
    return None


def insert_job(job: dict, existing_keys: set) -> bool:
    # I use a different date cutoff for full-time jobs (Jan 2026) vs internships (Sep 2025)
    cutoff = JOB_CUTOFF if job.get("type") == "Full-time Job" else CYCLE_CUTOFF
    if not is_date_relevant(job.get("deadline"), cutoff):
        return False

    # I skip dead links before touching the DB, but only for genuinely new URLs.
    # Re-HEAD-checking the thousands of already-stored URLs every run was the main
    # thing eating the time budget, and a known URL is never deleted even if it
    # 404s now, so that check was wasted work.
    url = job.get("url", "")
    if url and url not in _existing_urls and not is_url_alive(url):
        return False

    # New role with a description: let Groq fill any fields the ATS did not provide (bounded by
    # AI_BUDGET, never overriding an ATS value or touching user-owned columns).
    if url and url not in _existing_urls and job.get("description"):
        _ai_fill(job)

    key = dedupe_key(job["company"], job["role"], job.get("url", ""))

    record = {
        "company":  job["company"],
        "role":     job["role"],
        "type":     job.get("type", "internship"),
        # I use "scraped" so I can filter auto-discovered roles from ones I
        # manually added in the app.
        "status":       "scraped",
        "url":          url or None,
        "location":     normalize_location(job.get("location", "")),
        "notes":        job.get("notes", ""),
        # I leave applied_date as None because scraped roles have not been
        # applied to yet - they sit in "scraped" status until I pursue them.
        "applied_date": None,
        "deadline":     job.get("deadline"),
        "opening_date": job.get("opening_date"),
        "last_year_opening": job.get("last_year_opening"),
        "housing_location":  normalize_location(job.get("housing_location", "")) or None,
        "salary_range": job.get("salary_range", ""),
        "work_mode":    job.get("work_mode", ""),
        "source":       job.get("source", ""),
        # I default starred to False; I manually star interesting roles later.
        "starred":      False,
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
        "sponsors_visa": job.get("sponsors_visa", None),
        "category":     job.get("category") or detect_category(job["company"], job["role"]),
        # The app stores these as the text labels "Yes"/"No"/"Optional", so I write matching
        # strings rather than a Python bool that PostgREST would coerce to "true".
        "cv_required":            job.get("cv_required") or "Yes",
        "cover_letter_required":  _cover_letter_label(job.get("cover_letter_required")),
        "written_answers":        job.get("written_answers"),
    }
    # Only the scraper-owned columns are written to an existing row, and on a refresh I never overwrite
    # an AI-enriched field with an empty or regex value. category is left untouched (it is set on insert
    # or by the re-categorise backfill), and an empty value never clobbers one already there. This stops
    # the daily re-scrape from quietly reverting the AI categorisation and salary/work mode.
    patch = {
        k: v for k, v in record.items()
        if k in SCRAPER_FIELDS and k != "category" and v not in (None, "", [])
    }

    # Known URL -> refresh the scraper-owned fields in place. I never delete and never duplicate, and
    # status/notes/starred/applied_date stay exactly as I left them in the app.
    if url and url in _existing_urls:
        try:
            supabase.table("applications").update(patch).eq("url", url).execute()
        except Exception as e:
            print(f"  ~ update failed {job['company']}: {e}")
        _seen_urls.add(url)
        return False

    # URL-less duplicate already seen this run (no DB unique constraint protects these).
    if key in existing_keys:
        if url:
            _seen_urls.add(url)
        return False

    try:
        # A genuinely new row. Plain insert (not upsert-ignore) so a pre-load miss does not silently
        # drop the refresh - the 23505 path below turns a surprise URL conflict into a field update.
        supabase.table("applications").insert(record).execute()
        existing_keys.add(key)
        if url:
            _existing_urls.add(url)
            _seen_urls.add(url)
        if record.get("type") != "Full-time Job":
            _new_jobs.append(job)
        print(f"  + {job['company']} | {job['role']} {url}")
        return True
    except Exception as e:
        # 23505 = the URL already exists but the pre-load missed it (e.g. an RLS hiccup). Refresh the
        # scraper fields instead of dropping the row on the floor.
        if url and "23505" in str(e):
            try:
                supabase.table("applications").update(patch).eq("url", url).execute()
            except Exception:
                pass
            _existing_urls.add(url)
            _seen_urls.add(url)
            return False
        print(f"  ! Failed to insert {job['company']}: {e}")
        return False


def refresh_seen_timestamps() -> None:
    # I batch-update last_scraped_at for all entries seen this run so freshness
    # is always visible per-row, even though scraped applications are kept
    # permanently and never deleted. I only touch last_scraped_at - all other
    # columns (status, notes, starred etc.) remain exactly as the user left them.
    if not _seen_urls:
        return
    seen_list = list(_seen_urls)
    now = datetime.now(timezone.utc).isoformat()
    BATCH = 100
    try:
        for i in range(0, len(seen_list), BATCH):
            supabase.table("applications").update(
                {"last_scraped_at": now}
            ).in_("url", seen_list[i:i + BATCH]).execute()
        print(f"Refreshed timestamps for {len(seen_list)} existing entries.")
    except Exception as e:
        print(f"Warning: timestamp refresh failed: {e}")
