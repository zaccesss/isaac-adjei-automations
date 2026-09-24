"""
Fetches WakaTime daily summaries and per-hour durations for the last FETCH_DAYS
days and upserts each day into the wakatime_daily table.

Env vars required:
  WAKATIME_API_KEY          -- WakaTime secret API key
  SUPABASE_URL              -- Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY -- Supabase service-role key (bypasses RLS)
"""

import os
import sys
import time
from datetime import date, timedelta

import requests
from supabase import create_client

# fetch the last 14 days so a single missed run never leaves gaps.
FETCH_DAYS = 14

# on each run, also back-fill rows within this many days that are missing hourly or extra
# metrics (catches rows created before those columns existed). A one-off manual run can
# reach further back. Each run is capped so a big backlog drains over a few runs.
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "90") or 90)
MAX_BACKFILL_PER_RUN = int(os.environ.get("MAX_BACKFILL_PER_RUN", "120") or 120)

WAKATIME_API_KEY = os.environ.get("WAKATIME_API_KEY", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def fetch_summaries(start: date, end: date) -> list[dict]:
    """Call the WakaTime summaries endpoint for a date range."""
    url = "https://wakatime.com/api/v1/users/current/summaries"
    params = {"start": start.isoformat(), "end": end.isoformat()}
    try:
        resp = requests.get(url, params=params, auth=(WAKATIME_API_KEY, ""), timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        print(f"WakaTime summaries error: {exc}", file=sys.stderr)
        return []


def fetch_durations(day: date) -> list[dict]:
    """Call the WakaTime durations endpoint for a single day."""
    url = "https://wakatime.com/api/v1/users/current/durations"
    params = {"date": day.isoformat()}
    try:
        resp = requests.get(url, params=params, auth=(WAKATIME_API_KEY, ""), timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:
        print(f"WakaTime durations error for {day}: {exc}", file=sys.stderr)
        return []


def aggregate_hours(durations: list[dict]) -> list[int]:
    """
    Aggregate raw duration sessions into a 24-element array of seconds per UTC hour.
    Each session has time (Unix float) and duration (seconds float).
    """
    hours = [0] * 24
    for session in durations:
        t = session.get("time", 0)
        duration = session.get("duration", 0)
        if t and duration:
            hour = int((t % 86400) / 3600)
            hours[hour] += int(duration)
    return hours


def aggregate_ai(durations: list[dict]) -> dict:
    """
    Sum the per-duration AI metrics for one day. WakaTime reports GenAI and manually
    typed line changes, token counts, prompt stats and a USD cost per model.
    """
    ai = {
        "ai_additions": 0,
        "ai_deletions": 0,
        "human_additions": 0,
        "human_deletions": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "prompts": 0,
        "sessions": 0,
        "prompt_chars": 0,
        "costs": {},
    }
    for d in durations:
        ai["ai_additions"] += int(d.get("ai_additions") or 0)
        ai["ai_deletions"] += int(d.get("ai_deletions") or 0)
        ai["human_additions"] += int(d.get("human_additions") or 0)
        ai["human_deletions"] += int(d.get("human_deletions") or 0)
        ai["input_tokens"] += int(d.get("ai_input_tokens") or 0)
        ai["output_tokens"] += int(d.get("ai_output_tokens") or 0)
        ai["prompts"] += int(d.get("ai_prompt_events_total") or 0)
        ai["sessions"] += int(d.get("ai_sessions") or 0)
        ai["prompt_chars"] += int(d.get("ai_prompt_length_sum") or 0)
        for model, cost in (d.get("ai_model_costs") or {}).items():
            ai["costs"][model] = round(ai["costs"].get(model, 0) + float(cost or 0), 6)
    return ai


def top(items: list[dict], limit: int) -> list[dict]:
    """Keep the top entries by time as name and total_seconds pairs."""
    return sorted(
        [{"name": i["name"], "total_seconds": i["total_seconds"]} for i in items],
        key=lambda x: x["total_seconds"],
        reverse=True,
    )[:limit]


def build_row(day: dict, hours: list[int] | None = None, ai: dict | None = None) -> dict | None:
    """Convert one WakaTime summary day into a wakatime_daily row."""
    day_date = day.get("range", {}).get("date")
    if not day_date:
        return None
    total_seconds = day.get("grand_total", {}).get("total_seconds", 0)
    # keep top-10 per category to cap JSONB size.
    languages = sorted(
        [{"name": l["name"], "total_seconds": l["total_seconds"]} for l in day.get("languages", [])],
        key=lambda x: x["total_seconds"],
        reverse=True,
    )[:10]
    projects = sorted(
        [{"name": p["name"], "total_seconds": p["total_seconds"]} for p in day.get("projects", [])],
        key=lambda x: x["total_seconds"],
        reverse=True,
    )[:10]
    editors = sorted(
        [{"name": e["name"], "total_seconds": e["total_seconds"]} for e in day.get("editors", [])],
        key=lambda x: x["total_seconds"],
        reverse=True,
    )[:10]
    operating_systems = sorted(
        [{"name": o["name"], "total_seconds": o["total_seconds"]} for o in day.get("operating_systems", [])],
        key=lambda x: x["total_seconds"],
        reverse=True,
    )[:5]
    row = {
        "date": day_date,
        "total_seconds": int(total_seconds),
        "languages": languages,
        "projects": projects,
        "editors": editors,
        "operating_systems": operating_systems,
        "categories": top(day.get("categories", []), 10),
        "machines": top(day.get("machines", []), 5),
        "dependencies": top(day.get("dependencies", []), 15),
    }
    if hours is not None:
        row["hours"] = hours
    if ai is not None:
        row["ai"] = ai
    return row


def main() -> None:
    if not WAKATIME_API_KEY:
        print("WAKATIME_API_KEY not set - skipping sync", file=sys.stderr)
        sys.exit(0)
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Supabase credentials not set - skipping sync", file=sys.stderr)
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    end_date = date.today()
    start_date = end_date - timedelta(days=FETCH_DAYS - 1)

    print(f"Fetching WakaTime summaries {start_date} -> {end_date}")
    summary_data = fetch_summaries(start_date, end_date)
    print(f"  Got {len(summary_data)} day(s) from summaries")

    # build a date->day dict so we can match durations to summary days
    days_by_date: dict[str, dict] = {}
    for day in summary_data:
        d = day.get("range", {}).get("date")
        if d:
            days_by_date[d] = day

    # fetch durations for each day in the sync window (gives hourly breakdown)
    print(f"Fetching WakaTime durations for {FETCH_DAYS} days...")
    durations_by_date: dict[str, tuple[list[int], dict]] = {}
    cursor = start_date
    while cursor <= end_date:
        raw = fetch_durations(cursor)
        durations_by_date[cursor.isoformat()] = (aggregate_hours(raw), aggregate_ai(raw))
        cursor += timedelta(days=1)
        time.sleep(0.2)  # be polite to the API

    # build rows for upsert
    rows = []
    for day_date, day in days_by_date.items():
        hours, ai = durations_by_date.get(day_date, (None, None))
        row = build_row(day, hours=hours, ai=ai)
        if row:
            rows.append(row)

    if not rows:
        print("No rows to upsert - nothing to do")
    else:
        result = (
            supabase.table("wakatime_daily")
            .upsert(rows, on_conflict="date")
            .execute()
        )
        print(f"  Upserted {len(rows)} row(s) with hourly data")

    # back-fill hourly and AI data for recent rows that predate those columns
    backfill_start = (end_date - timedelta(days=BACKFILL_DAYS - 1)).isoformat()
    existing = (
        supabase.table("wakatime_daily")
        .select("date")
        .gte("date", backfill_start)
        .or_("hours.is.null,ai.is.null,categories.is.null,dependencies.is.null")
        .order("date", desc=True)
        .execute()
    )
    backfill_dates = [r["date"] for r in (existing.data or [])]
    # skip dates already fetched above
    recent_fetched = set(days_by_date.keys())
    backfill_dates = [d for d in backfill_dates if d not in recent_fetched]
    remaining = max(0, len(backfill_dates) - MAX_BACKFILL_PER_RUN)
    backfill_dates = backfill_dates[:MAX_BACKFILL_PER_RUN]

    if backfill_dates:
        print(f"Back-filling {len(backfill_dates)} row(s) missing hourly or extra metrics ({remaining} left for later runs)...")
        first = date.fromisoformat(min(backfill_dates))
        last = date.fromisoformat(max(backfill_dates))
        older_summaries = {
            d.get("range", {}).get("date"): d for d in fetch_summaries(first, last)
        }
        for d_str in sorted(backfill_dates):
            raw = fetch_durations(date.fromisoformat(d_str))
            hours, ai = aggregate_hours(raw), aggregate_ai(raw)
            day = older_summaries.get(d_str)
            row = build_row(day, hours=hours, ai=ai) if day else None
            if row:
                supabase.table("wakatime_daily").upsert(row, on_conflict="date").execute()
            else:
                supabase.table("wakatime_daily").update({"hours": hours, "ai": ai}).eq("date", d_str).execute()
            print(f"  Back-filled {d_str}")
            time.sleep(0.2)

    time.sleep(0.5)


if __name__ == "__main__":
    from lib.report_failure import guard

    with guard("wakatime-sync"):
        main()
