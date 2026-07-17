# Scripts

The actual work behind each [workflow](../.github/workflows/README.md). Every script is
self-contained and takes all of its runtime settings from environment variables (injected from GitHub
Actions secrets), so nothing configurable is committed and the repo can stay public. The Node scripts
are `.mjs` with no dependencies (global `fetch`); the Python scripts install from
[`requirements.txt`](requirements.txt).

## What each script does

| Script | Lang | Runs from | Purpose |
| --- | --- | --- | --- |
| [`wakatime-sync.py`](wakatime-sync.py) | Python | wakatime-sync, daily-coding-summary | Fetches WakaTime daily totals and per-hour durations and upserts them into `wakatime_daily` (`on_conflict=date`, so re-runs are safe) |
| [`daily-coding-summary.mjs`](daily-coding-summary.mjs) | Node | daily-coding-summary | Posts the Discord coding recap for the day that just ended, comparing it to the 30-day average |
| [`routine.mjs`](routine.mjs) | Node | routine | Reads the day's habits and streaks and posts a morning checklist to Discord |
| [`send-streak-reminder.mjs`](send-streak-reminder.mjs) | Node | streak-reminder | Posts which active streaks are not yet logged today |
| [`vault-expiry-check.mjs`](vault-expiry-check.mjs) | Node | vault-expiry-check | Alerts when vault or `inventory_items` entries are near their expiry date |
| [`daily-analytics.mjs`](daily-analytics.mjs) | Node | daily-analytics | Posts a per-page analytics summary (Applications, Posts, Fitness, Music) to each dashboard analytics channel for the day that just ended |
| [`medication-reminders.mjs`](medication-reminders.mjs) | Node | medication-reminders | Sends due medication reminders to Discord, email or SMS, de-duplicated against a dose log |
| [`reminders.mjs`](reminders.mjs) | Node | reminders | Sends one-off appointment and meeting reminders at their lead times, each stamped so none repeats |
| [`spotify-history.mjs`](spotify-history.mjs) | Node | spotify-history | Records recent Spotify plays into `listening_history` for the listening analytics |
| [`recategorise.py`](recategorise.py) | Python | recategorise | Re-categorises "Software Engineering" catch-all applications with the AI (dry-run by default on manual runs) |
| [`job-scraper.py`](job-scraper.py) | Python | job-scraper | Scrapes graduate and internship sources (ATS REST APIs including Workable, Recruitee, Personio and Jibe, the LinkedIn guest search, HTML boards via curl_cffi with a Scrapling Camoufox fallback that solves Cloudflare, rendered boards like Prospects and TARGETjobs, plus a Playwright pass) and upserts them into the applications table, collapsing the same job from two sources onto one row |

## Shared helper

[`lib/uk-cron.mjs`](lib/uk-cron.mjs) provides the UK-time helpers the message-sending jobs share:
`londonHour()` / `londonDate()` for the gate, and `alreadyRanToday(job)`, which claims `(job, run_date)`
in the `cron_runs` table so a delayed run cannot double-post. `FORCE=1` (set on a manual
`workflow_dispatch`) bypasses the claim. See the
[workflows README](../.github/workflows/README.md#uk-time-and-the-windowed-schedule) for the full pattern.

## Environment

Every script reads its config from the environment. The full list of secret names, with placeholders,
is in [`.env.example`](../.env.example); real values live only as GitHub Actions secrets and are never
committed. Common to almost all scripts: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (the
service-role key bypasses RLS). The secrets each script additionally needs:

| Script | Additional secrets |
| --- | --- |
| `wakatime-sync.py` | `WAKATIME_API_KEY` |
| `daily-coding-summary.mjs` | `DISCORD_WEBHOOK_CODING` |
| `routine.mjs` | `DISCORD_WEBHOOK_ROUTINE` |
| `send-streak-reminder.mjs` | `DISCORD_WEBHOOK_STREAKS` |
| `vault-expiry-check.mjs` | `DISCORD_WEBHOOK_VAULT` |
| `daily-analytics.mjs` | `DISCORD_WEBHOOK_APPLICATIONS`, `DISCORD_WEBHOOK_POSTS`, `DISCORD_WEBHOOK_FITNESS`, `DISCORD_WEBHOOK_MUSIC` (each optional; a channel is skipped if its webhook is unset) |
| `medication-reminders.mjs`, `reminders.mjs` | `DISCORD_WEBHOOK_REMINDERS`, `RESEND_API_KEY`, `REMINDER_FROM_EMAIL`, and `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` for SMS |
| `spotify-history.mjs` | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN` |
| `recategorise.py` | one of `GROQ_API_KEY` / `GOOGLE_AI_API_KEY` / `OPENROUTER_API_KEY` / `GH_MODELS_TOKEN` |
| `job-scraper.py` | job-board keys (`ADZUNA_APP_ID` / `ADZUNA_APP_KEY`, `REED_API_KEY`, `JOOBLE_API_KEY`), an AI key for categorisation (as above) and `DISCORD_WEBHOOK_URL` for the run summary |

Some scripts also read **optional behaviour flags** that are not secrets and that you do not provision:
the workflows set them and the code has sensible defaults. These are `SCRAPER_MODE` /
`SCRAPER_BUDGET_MIN` / `SCRAPER_AI_BUDGET` / `SCRAPER_AI_TEST` (job-scraper), `RECATEGORISE_DRY_RUN`
(recategorise), `FORCE` (bypasses the UK-hour gate and idempotency on a manual run) and `TEST_EMAIL` /
`TEST_TO` (a one-off test send from the reminder jobs). They are listed, commented, at the bottom of
[`.env.example`](../.env.example). The authoritative environment for each job is the `env:` block in its
[workflow](../.github/workflows/README.md).

Monitoring is handled at the workflow level, not in the scripts: each workflow pings Healthchecks.io on
start, success and fail through the shared [`../.github/actions/healthcheck`](../.github/actions/healthcheck/action.yml)
action, guarded on the `HEALTHCHECK_PING_KEY` secret. See
[Monitoring](../.github/workflows/README.md#monitoring).

## Running one locally

Export the variables above (or source them from a local env file that is never committed) and run the
script directly, for example `node scripts/routine.mjs` or `python scripts/wakatime-sync.py`. Set
`FORCE=1` to bypass the UK-hour gate and idempotency on the jobs that support it.
