"""Supabase access: dedupe keys, existing-row loading, the insert-or-refresh upsert and the freshness stamp."""

import re

from . import config
from datetime import datetime, timedelta, timezone
from .ai import _ai_fill
from .dates import CYCLE_CUTOFF, JOB_CUTOFF, is_date_relevant
from .filters import _NON_TECH_ROLE_RE, _has_tech_keyword, detect_category, infer_type
from .http import is_url_alive
from .locations import MULTI_LOCATION_RE, is_abroad, is_uk, normalize_location
from .roles import classify, in_cycle



# ─── DEDUPLICATION ──────────────────────────────────────────────────────────

def dedupe_key(company: str, role: str, url: str = "") -> str:
    # prefer URL-based deduplication so the same job posting scraped from
    # two different sources is never inserted twice. Trailing slashes are stripped
    # because the same URL can appear with and without one.
    if url and url.startswith("http"):
        # normalise both Greenhouse URL domains to the old format so rows
        # inserted before the domain change (boards.greenhouse.io) and rows
        # inserted after (job-boards.greenhouse.io) hash to the same key and
        # never trigger a 23505 unique constraint violation.
        url = url.replace("job-boards.greenhouse.io", "boards.greenhouse.io")
        raw = url.strip().rstrip("/")
    else:
        # fall back to company+role when there is no URL. Both fields are lower-cased and
        # stripped so "Google" and "google" hash identically.
        # the employer's cleaned name, so "Barclays" and "Barclays Bank Plc" are one company
        raw = f"{company_key(company)}|{re.sub(r'[^a-z0-9]+', ' ', role.lower()).strip()}"
    # the normalised text is the key itself. Keys only live in memory and are rebuilt from the table each run, so there is
    # nothing to hash: a plain string compares exactly, cannot collide and is not sensitive data being run through a hash.
    return raw


# boards and aggregators: their links point at their own posting page, not the
# employer's application page, so a direct ATS or company link always beats one.
_AGGREGATOR_RE = re.compile(
    r"linkedin\.com|milkround\.com|totaljobs\.com|studentjob\.co\.uk|"
    r"e4s\.co\.uk|targetjobs\.co\.uk|prospects\.ac\.uk|gradcracker\.com|"
    r"brightnetwork\.co\.uk|ratemyplacement\.co\.uk|reed\.co\.uk|adzuna|"
    r"jooble|jobicy\.com|remotive\.(?:com|io)|arbeitnow\.com|indeed\.com",
    re.I,
)


def url_rank(url: str) -> int:
    """2 for a direct company or ATS link, 1 for a board or aggregator page, 0 for none.

    Used to decide which link a job keeps when two sources carry the same role
    under different URLs: the one that lands on the employer's own application
    page wins over one that lands on a board's posting page.
    """
    if not url or not url.startswith("http"):
        return 0
    return 1 if _AGGREGATOR_RE.search(url) else 2


def load_existing_keys(ctx) -> None:
    # load all existing keys at the start of each run so every insert check
    # is an O(1) set lookup rather than a DB query per row. PostgREST caps a
    # single response at 1000 rows and this table passed that long ago, so the
    # read pages in batches - a bare select silently stopped at the first 1000,
    # which made every older row look brand new on every run (a wasted liveness
    # check and AI call each, saved only by the 23505 fallback).
    try:
        for start in range(0, 200_000, 1000):
            res = ctx.supabase.table("applications").select(
                "company,role,url"
            ).range(start, start + 999).execute()
            rows = res.data or []
            ctx.existing_keys.update(
                dedupe_key(r["company"], r["role"], r.get("url") or "") for r in rows
            )
            # remember which URLs already exist so insert_job updates them in place rather than skipping.
            ctx.existing_urls.update(r["url"] for r in rows if r.get("url"))
            # and the best link already stored per company+role, so the same job
            # arriving from another source under a different URL is recognised
            # instead of inserted again.
            for r in rows:
                u = r.get("url") or ""
                if not u:
                    continue
                bare = dedupe_key(r["company"], r["role"], "")
                if url_rank(u) > url_rank(ctx.url_by_bare_key.get(bare, "")):
                    ctx.url_by_bare_key[bare] = u
            if len(rows) < 1000:
                break
        # every place the map has already pinned in Great Britain counts as UK, which covers the
        # towns no fixed list can (Fleet, Bracknell's villages, a business park's own name)
        for start in range(0, 50_000, 1000):
            res = ctx.supabase.table("location_geocodes").select("location").eq(
                "country_code", "GB"
            ).range(start, start + 999).execute()
            places = res.data or []
            ctx.uk_places.update((r.get("location") or "").strip().lower() for r in places)
            if len(places) < 1000:
                break
        if not ctx.existing_keys:
            # warn here because an empty result on a populated DB usually
            # means RLS is blocking the SELECT - the upsert below will still
            # prevent duplicates at the DB level so this is non-fatal.
            print("WARNING: 0 existing rows loaded - RLS may be blocking reads. Continuing with upsert deduplication.")
    except Exception as e:
        # log and continue rather than crashing - the upsert strategy means
        # no duplicates are created even if this pre-load fails.
        print(f"Warning: could not load existing keys: {e}")


# ─── INSERT ─────────────────────────────────────────────────────────────────



# columns the scraper owns and may overwrite on an existing row. Everything else (status, notes,
# starred, applied_date) is user-owned and is NEVER touched on an update, so a re-scrape refreshes
# stale data - including the CV / cover letter / written-answers facts now read from The Trackr -
# without clobbering edits made in the app.
SCRAPER_FIELDS = {
    "company", "role", "type", "location", "deadline", "opening_date",
    "salary_range", "work_mode", "source", "sponsors_visa", "category", "last_scraped_at",
    "last_year_opening", "housing_location", "cv_required", "cover_letter_required",
    "written_answers", "abroad", "description",
}


def _cover_letter_label(v):
    # scrapers pass True/False/None (or occasionally a string); the app stores the text labels
    # "Yes"/"No"/"Optional", so normalise to that rather than a Python bool that becomes "true".
    if v is True:
        return "Yes"
    if v is False:
        return "No"
    if isinstance(v, str) and v.strip():
        return v
    return None


# the kinds of role kept for the Abroad tab when they are outside the UK
STUDENT_KINDS = {"internship", "placement", "insight", "graduate"}

# boards that list UK roles only, so a listing with no location from them is still a UK role
UK_ONLY_BOARDS = {
    "Gradcracker", "TARGETjobs", "Milkround", "RateMyPlacement", "Prospects", "Bright Network",
    "The Trackr", "StudentJob", "E4S", "Reed", "Adzuna", "Jooble",
}
# a title that names a country or city abroad outranks a London location field
_TITLE_ABROAD = re.compile(
    r"\b(united states|usa|u\.s\.|new york|san francisco|seattle|boston|chicago|texas|california|canada|"
    r"toronto|vancouver|australia|sydney|melbourne|ireland|dublin|india|bangalore|singapore|hong kong|"
    r"germany|berlin|munich|france|paris|netherlands|amsterdam|spain|madrid|switzerland|zurich|poland|"
    r"warsaw|japan|tokyo|china|shanghai|brazil|sao paulo|mexico|dubai)\b",
    re.IGNORECASE,
)
_TITLE_UK = re.compile(r"\b(uk|united kingdom|london|england|scotland|wales|northern ireland|glasgow|edinburgh|manchester|belfast)\b", re.IGNORECASE)


def company_key(company: str) -> str:
    """An employer's name without case, punctuation or endings: "Barclays Bank Plc" is "barclays"."""
    name = re.sub(r"[^a-z0-9 ]+", " ", (company or "").lower())
    name = re.sub(r"\b(plc|ltd|limited|llp|llc|inc|corp|corporation|group|holdings|company|co|the|uk|ireland|"
                  r"bank|international|technologies|technology|semiconductors|industries|lp|l p)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def salary_text(job: dict) -> str:
    """A tidy annual salary from a source's own minimum and maximum; its own text when it has one.

    Figures under 5,000 are daily or hourly rates the boards do not label, so they are left out.
    """
    if job.get("salary_range"):
        return job["salary_range"]
    vals = []
    for k in ("salary_min", "salary_max"):
        try:
            v = float(job.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v >= 5000:
            vals.append(round(v))
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    return f"£{lo:,}" if lo == hi else f"£{lo:,} to £{hi:,}"


def plain_date(value):
    """An ISO date from the forms sources use (2026-10-08, 2026-10-08T... and 08/10/2026)."""
    if not value:
        return None
    v = str(value).strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return v[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", v) else None


def gate(job: dict, uk_places=frozenset()):
    """The reason a role is kept off the dashboard; None when it may be stored.

    The same rules Vitafolio applies: no apprenticeships, nothing outside the recruitment cycle
    and UK roles only. A blank location is trusted only from a UK-only board.
    """
    role = job.get("role", "")
    if _NON_TECH_ROLE_RE.search(role) or not _has_tech_keyword(role.lower()):
        return "not a tech or engineering role"
    if classify(role) == "apprenticeship":
        return "apprenticeship"
    if not in_cycle(role):
        return "outside the cycle"
    location = job.get("location") or ""
    title_abroad = _TITLE_ABROAD.search(re.sub(r"northern ireland", " ", role, flags=re.IGNORECASE))
    if title_abroad and not _TITLE_UK.search(role):
        location = title_abroad.group(0)
    known_uk = location.strip().lower() in uk_places
    if is_uk(location) or known_uk or (not location.strip() and job.get("source") in UK_ONLY_BOARDS):
        return None
    # abroad needs positive evidence (a country, a US state, a known foreign city); a student role
    # there is kept for the Abroad tab
    if is_abroad(location):
        return "abroad" if classify(role) in STUDENT_KINDS else "outside the UK"
    # a bare "Remote", a "2 Locations" placeholder or a blank from a global board names no country
    vague = re.fullmatch(r"\s*(remote|hybrid|anywhere|worldwide|global|multiple locations)?\s*", location, re.IGNORECASE)
    if vague or MULTI_LOCATION_RE.match(location):
        return "outside the UK"
    # any other named place is most often a small UK town no list can hold (Brixworth, Thursley,
    # Barrow-in-Furness), since foreign places are caught above
    return None


def insert_job(ctx, job: dict) -> bool:
    reason = gate(job, ctx.uk_places)
    job["abroad"] = reason == "abroad"
    # the tab comes from the title; only a UK student board may call an untitled role an internship
    titled = infer_type(job["role"], default="")
    if titled:
        job["type"] = titled
    elif job.get("source") not in UK_ONLY_BOARDS:
        job["type"] = "Full-time Job"
    if reason == "abroad":
        reason = None
    if reason:
        ctx.gate_rejects[reason] = ctx.gate_rejects.get(reason, 0) + 1
        return False
    # the date cutoff differs by type (both sit at Jan 2026 this season)
    cutoff = JOB_CUTOFF if job.get("type") == "Full-time Job" else CYCLE_CUTOFF
    if not is_date_relevant(job.get("deadline"), cutoff):
        return False

    # skip dead links before touching the DB, but only for genuinely new URLs.
    # re-HEAD-checking the thousands of already-stored URLs every run was the main
    # thing eating the time budget and a known URL is never deleted even if it
    # 404s now, so that check was wasted work.
    url = job.get("url", "")
    if url and url not in ctx.existing_urls and not is_url_alive(url):
        return False

    # new role with a description: let Groq fill any fields the ATS did not provide (bounded by
    # AI_BUDGET, never overriding an ATS value or touching user-owned columns).
    if url and url not in ctx.existing_urls and job.get("description"):
        _ai_fill(ctx, job)

    key = dedupe_key(job["company"], job["role"], job.get("url", ""))

    # an existing url-less row with this company and role gets its URL filled in
    # place instead of gaining a linked lookalike: a fallback URL changes the
    # url-based key, so the plain key match below would never see the old row.
    if url and key not in ctx.existing_keys:
        bare_key = dedupe_key(job["company"], job["role"], "")
        if bare_key in ctx.existing_keys and url not in ctx.existing_urls:
            if config.DRY_RUN:
                ctx.dry_run_actions.append(("fill-url", job["company"], job["role"]))
                print(f"  [dry run] would fill url for {job['company']} | {job['role']}")
            else:
                try:
                    ctx.supabase.table("applications").update({"url": url}).eq(
                        "company", job["company"]
                    ).eq("role", job["role"]).eq(
                        "status", "scraped"
                    ).is_("url", "null").execute()
                except Exception as e:
                    print(f"  ~ url fill failed {job['company']}: {type(e).__name__}")
            ctx.existing_keys.add(key)
            ctx.existing_urls.add(url)
            ctx.seen_urls.add(url)
            return False

    # the same company+role stored under a different link is the same posting
    # seen through another source - a board, LinkedIn and the employer's ATS
    # each carry their own URL for one job. A second row is never inserted for it.
    # when the new link is more direct than the stored one, the
    # scraped row's URL is upgraded in place; progressed rows and user-owned fields are
    # never touched and an equal or worse link just marks the row as seen.
    if url and key not in ctx.existing_keys:
        bare_key = dedupe_key(job["company"], job["role"], "")
        prev_url = ctx.url_by_bare_key.get(bare_key, "")
        if prev_url and prev_url != url:
            if url_rank(url) > url_rank(prev_url):
                if config.DRY_RUN:
                    ctx.dry_run_actions.append(("upgrade-url", job["company"], job["role"]))
                    print(f"  [dry run] would upgrade url for {job['company']} | {job['role']}")
                else:
                    try:
                        ctx.supabase.table("applications").update({"url": url}).eq(
                            "url", prev_url
                        ).eq("status", "scraped").execute()
                    except Exception as e:
                        print(f"  ~ url upgrade failed {job['company']}: {type(e).__name__}")
                ctx.url_by_bare_key[bare_key] = url
                ctx.existing_keys.add(key)
                ctx.existing_urls.add(url)
                ctx.seen_urls.add(url)
            else:
                ctx.seen_urls.add(prev_url)
            return False

    record = {
        "company":  job["company"],
        "role":     job["role"],
        "type":     job.get("type", "internship"),
        # use "scraped" so auto-discovered roles can be filtered from ones
        # added by hand in the app.
        "status":       "scraped",
        "url":          url or None,
        "location":     normalize_location(job.get("location", "")),
        "notes":        job.get("notes", ""),
        # leave applied_date as None because scraped roles have not been
        # applied to yet - they sit in "scraped" status until someone pursues them.
        "applied_date": None,
        "deadline":     plain_date(job.get("deadline")),
        "opening_date": plain_date(job.get("opening_date")),
        "last_year_opening": job.get("last_year_opening"),
        "housing_location":  normalize_location(job.get("housing_location", "")) or None,
        "salary_range": salary_text(job),
        "work_mode":    job.get("work_mode", ""),
        "source":       job.get("source", ""),
        # default starred to False; interesting roles are starred by hand later.
        "starred":      False,
        "last_scraped_at": datetime.now(timezone.utc).isoformat(),
        "sponsors_visa": job.get("sponsors_visa", None),
        "category":     detect_category(job["company"], job["role"]),
        # the app stores these as the text labels "Yes"/"No"/"Optional", so the scraper writes matching
        # strings rather than a Python bool that PostgREST would coerce to "true".
        "cv_required":            job.get("cv_required") or "Yes",
        "cover_letter_required":  _cover_letter_label(job.get("cover_letter_required")),
        "written_answers":        job.get("written_answers"),
        "abroad":       bool(job.get("abroad")),
        # the advert as the source gives it, capped so one row never carries a whole careers site
        "description":  (job.get("description") or "")[:20000] or None,
    }
    # only the scraper-owned columns are written to an existing row. A refresh never overwrites
    # an AI-enriched field with an empty or regex value. category is left untouched (it is set on insert
    # or by the re-categorise backfill) and an empty value never clobbers one already there. This stops
    # the daily re-scrape from quietly reverting the AI categorisation and salary/work mode.
    patch = {
        k: v for k, v in record.items()
        # category is deterministic now, so a refresh corrects one filed under older rules
        if k in SCRAPER_FIELDS and v not in (None, "", [])
    }

    # known URL -> refresh the scraper-owned fields in place. Nothing is deleted or duplicated.
    # status/notes/starred/applied_date stay exactly as they were left in the app.
    if url and url in ctx.existing_urls:
        if config.DRY_RUN:
            ctx.dry_run_actions.append(("update", job["company"], job["role"]))
            print(f"  [dry run] would update {job['company']} | {job['role']}")
        else:
            try:
                ctx.supabase.table("applications").update(patch).eq("url", url).execute()
            except Exception as e:
                print(f"  ~ update failed {job['company']}: {e}")
        ctx.seen_urls.add(url)
        return False

    # URL-less duplicate already seen this run (no DB unique constraint protects these).
    if key in ctx.existing_keys:
        if url:
            ctx.seen_urls.add(url)
            # a row inserted back when this job carried no URL sits linkless forever
            # otherwise (the update path matches by URL, which it does not have).
            # fill the URL onto the matching url-less scraped row; user-owned fields
            # stay untouched and progressed rows are excluded by status.
            if url not in ctx.existing_urls:
                if config.DRY_RUN:
                    ctx.dry_run_actions.append(("fill-url", job["company"], job["role"]))
                    print(f"  [dry run] would fill url for {job['company']} | {job['role']}")
                else:
                    try:
                        ctx.supabase.table("applications").update({"url": url}).eq(
                            "company", job["company"]
                        ).eq("role", job["role"]).eq(
                            "status", "scraped"
                        ).is_("url", "null").execute()
                    except Exception as e:
                        print(f"  ~ url fill failed {job['company']}: {type(e).__name__}")
                ctx.existing_urls.add(url)
        return False

    if config.DRY_RUN:
        ctx.existing_keys.add(key)
        if url:
            ctx.existing_urls.add(url)
            ctx.seen_urls.add(url)
            bare_key = dedupe_key(job["company"], job["role"], "")
            if url_rank(url) > url_rank(ctx.url_by_bare_key.get(bare_key, "")):
                ctx.url_by_bare_key[bare_key] = url
        if record.get("type") != "Full-time Job":
            ctx.new_jobs.append(job)
        ctx.dry_run_actions.append(("insert", job["company"], job["role"]))
        print(f"  [dry run] would insert {job['company']} | {job['role']} {url}")
        return True

    try:
        # a genuinely new row. Plain insert (not upsert-ignore) so a pre-load miss does not silently
        # drop the refresh - the 23505 path below turns a surprise URL conflict into a field update.
        ctx.supabase.table("applications").insert(record).execute()
        ctx.existing_keys.add(key)
        if url:
            ctx.existing_urls.add(url)
            ctx.seen_urls.add(url)
            bare_key = dedupe_key(job["company"], job["role"], "")
            if url_rank(url) > url_rank(ctx.url_by_bare_key.get(bare_key, "")):
                ctx.url_by_bare_key[bare_key] = url
        if record.get("type") != "Full-time Job":
            ctx.new_jobs.append(job)
        print(f"  + {job['company']} | {job['role']} {url}")
        return True
    except Exception as e:
        # 23505 = the URL already exists but the pre-load missed it (e.g. an RLS hiccup). Refresh the
        # scraper fields instead of dropping the row on the floor.
        if url and "23505" in str(e):
            try:
                ctx.supabase.table("applications").update(patch).eq("url", url).execute()
            except Exception:
                pass
            ctx.existing_urls.add(url)
            ctx.seen_urls.add(url)
            return False
        print(f"  ! Failed to insert {job['company']}: {type(e).__name__}")
        return False


def archive_stale(ctx) -> None:
    """Archive scraped roles that have closed or that no scrape has seen for 14 days.

    Archiving hides a row without deleting it. Rows that have been worked on (any status other
    than scraped) are never touched.
    """
    if config.DRY_RUN:
        print("[dry run] would archive stale and closed scraped roles.")
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        stale = ctx.supabase.table("applications").update({"archived": True}).eq("status", "scraped") \
            .eq("archived", False).lt("last_scraped_at", cutoff).execute()
        closed = ctx.supabase.table("applications").update({"archived": True}).eq("status", "scraped") \
            .eq("archived", False).lt("deadline", today).execute()
        print(f"Archived {len(stale.data or [])} stale and {len(closed.data or [])} closed roles.")
    except Exception as e:
        print(f"Warning: archiving stale roles failed: {type(e).__name__}")


def refresh_seen_timestamps(ctx) -> None:
    # batch-update last_scraped_at for all entries seen this run so freshness
    # is always visible per-row, even though scraped applications are kept
    # permanently and never deleted. Only last_scraped_at is touched - all other
    # columns (status, notes, starred etc.) remain exactly as the user left them.
    if not ctx.seen_urls:
        return
    if config.DRY_RUN:
        print(f"[dry run] would refresh timestamps for {len(ctx.seen_urls)} existing entries.")
        return
    seen_list = list(ctx.seen_urls)
    now = datetime.now(timezone.utc).isoformat()
    BATCH = 100
    try:
        for i in range(0, len(seen_list), BATCH):
            ctx.supabase.table("applications").update(
                {"last_scraped_at": now}
            ).in_("url", seen_list[i:i + BATCH]).execute()
        print(f"Refreshed timestamps for {len(seen_list)} existing entries.")
    except Exception as e:
        print(f"Warning: timestamp refresh failed: {e}")
