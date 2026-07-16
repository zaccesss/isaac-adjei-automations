"""One-off backfill: move already-scraped rows to their correct type tabs.

The Trackr scraper spent a while stamping rows with whichever category page reached
them first (all four routes serve the same table), and rows without an external
apply link never take the update path that would have healed them on re-scrape.
This recomputes each scraped row's type from its own title, exactly as the scraper
does now. A title with no student signal at all resolves to Full-time Job (it was
never an internship, placement or event, whatever tab it sat in); student-facing
titles without a specific type term keep their current value.

Only rows with status='scraped' are touched (type is scraper-owned on those; rows
I have progressed stay exactly as I left them). Ghost rows whose role equals their
company (the old parser's failure mode) cannot be retyped because there is no real
role to recover - they are listed and left alone unless FIX_GHOSTS=1 explicitly
asks for their deletion.

DRY_RUN=1 (the default in the workflow) prints every change it would make and
writes nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client  # noqa: E402

from datetime import datetime, timedelta, timezone  # noqa: E402

from scraper.filters import is_relevant, resolve_type  # noqa: E402

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
DRY_RUN = os.environ.get("DRY_RUN", "1").strip() != "0"
FIX_GHOSTS = os.environ.get("FIX_GHOSTS", "").strip() == "1"
FIX_DUPES = os.environ.get("FIX_DUPES", "").strip() == "1"
PURGE_STALE = os.environ.get("PURGE_STALE", "").strip() == "1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def main():
    rows = []
    for start in range(0, 200_000, 1000):
        res = supabase.table("applications").select(
            "id,company,role,type,source,location,last_scraped_at,url"
        ).eq("status", "scraped").range(start, start + 999).execute()
        page = res.data or []
        rows.extend(page)
        if len(page) < 1000:
            break
    print(f"{len(rows)} scraped rows loaded")

    retyped = 0
    ghosts = []
    for r in rows:
        company = (r.get("company") or "").strip()
        role = (r.get("role") or "").strip()
        current = r.get("type") or "Internship"
        if role and company and role.lower() == company.lower():
            ghosts.append(r)
            continue
        expected = resolve_type(role, fallback=current)
        if expected != current:
            print(f"  retype {company} | {role}: {current} -> {expected}")
            retyped += 1
            if not DRY_RUN:
                supabase.table("applications").update(
                    {"type": expected}
                ).eq("id", r["id"]).execute()

    print(f"\n{retyped} rows {'would be' if DRY_RUN else ''} retyped")

    # Report-only: rows the strengthened filters would no longer accept at all
    # (commercial titles, non-tech roles) and rows the boards have stopped listing
    # (no freshness stamp for 14 days). Nothing here is changed or deleted - these
    # counts are the evidence for a separate, explicitly approved clean-up.
    irrelevant = [
        r for r in rows
        if (r.get("role") or "") and (r.get("company") or "")
        and not is_relevant(r["role"], r["company"], r.get("location") or "")
    ]
    print(f"\n{len(irrelevant)} rows would no longer pass todays filters (report only):")
    for r in irrelevant[:20]:
        print(f"  no-longer-relevant: {r['company']} | {r['role']}")
    if len(irrelevant) > 20:
        print(f"  ... plus {len(irrelevant) - 20} more")

    # My healing bug briefly inserted linked twins next to old url-less rows:
    # where a company-and-role pair has both, the url-less copy is redundant.
    by_pair = {}
    for r in rows:
        pair = ((r.get("company") or "").strip().lower(), (r.get("role") or "").strip().lower())
        by_pair.setdefault(pair, []).append(r)
    dupes = []
    for pair, group in by_pair.items():
        if len(group) > 1 and any(g.get("url") for g in group):
            dupes.extend(g for g in group if not g.get("url"))
    print(f"\n{len(dupes)} url-less duplicate rows (a linked twin exists):")
    for d in dupes[:15]:
        print(f"  dupe: {d['company']} | {d['role']}")
    if dupes and FIX_DUPES and not DRY_RUN:
        for d in dupes:
            supabase.table("applications").delete().eq("id", d["id"]).execute()
        print(f"deleted {len(dupes)} url-less duplicates (FIX_DUPES=1)")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    dupe_ids = {d["id"] for d in dupes}
    stale = [
        r for r in rows
        if (r.get("last_scraped_at") or "") < cutoff and r["id"] not in dupe_ids
    ]
    print(f"\n{len(stale)} rows not seen by any scrape in 14 days (dead listings)")
    if stale and PURGE_STALE and not DRY_RUN:
        for r in stale:
            supabase.table("applications").delete().eq("id", r["id"]).execute()
        print(f"deleted {len(stale)} stale scraped rows (PURGE_STALE=1) - progressed rows are never touched")

    print(f"\n{len(ghosts)} ghost rows (role equals company, unrecoverable):")
    for g in ghosts:
        print(f"  ghost {g.get('source') or '?'}: {g['company']} | {g['role']}")
    if ghosts and FIX_GHOSTS and not DRY_RUN:
        for g in ghosts:
            supabase.table("applications").delete().eq("id", g["id"]).execute()
        print(f"deleted {len(ghosts)} ghost rows (FIX_GHOSTS=1)")
    elif ghosts:
        print("ghosts left untouched (set FIX_GHOSTS=1 with DRY_RUN=0 to delete them)")


if __name__ == "__main__":
    main()
