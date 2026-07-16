"""One-off backfill: move already-scraped rows to their correct type tabs.

The Trackr scraper spent a while stamping rows with whichever category page reached
them first (all four routes serve the same table), and rows without an external
apply link never take the update path that would have healed them on re-scrape.
This recomputes each scraped row's type from its own title, exactly as the scraper
does now, and only changes rows whose title carries a real signal: infer_type gets
the row's current type as the default, so a title with no placement, spring, grad,
event or intern term keeps whatever it has.

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

from scraper.filters import infer_type  # noqa: E402

SUPABASE_URL = os.environ["SUPABASE_URL"].strip()
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
DRY_RUN = os.environ.get("DRY_RUN", "1").strip() != "0"
FIX_GHOSTS = os.environ.get("FIX_GHOSTS", "").strip() == "1"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def main():
    rows = []
    for start in range(0, 200_000, 1000):
        res = supabase.table("applications").select(
            "id,company,role,type,source"
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
        expected = infer_type(role, default=current)
        if expected != current:
            print(f"  retype {company} | {role}: {current} -> {expected}")
            retyped += 1
            if not DRY_RUN:
                supabase.table("applications").update(
                    {"type": expected}
                ).eq("id", r["id"]).execute()

    print(f"\n{retyped} rows {'would be' if DRY_RUN else ''} retyped")

    print(f"{len(ghosts)} ghost rows (role equals company, unrecoverable):")
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
