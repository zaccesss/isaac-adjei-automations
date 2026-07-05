# Workflows

Every job is a GitHub Actions workflow here, wrapping a script in [`../../scripts`](../../scripts).
The scheduled jobs are split into two groups: the scheduled jobs that do the actual work, and the
repo-automation workflows that keep the repository itself healthy.

## Scheduled jobs

| Workflow | Schedule | Script | Purpose |
| --- | --- | --- | --- |
| [daily-coding-summary](daily-coding-summary.yml) | 00:30 UK | [`wakatime-sync.py`](../../scripts/wakatime-sync.py) then [`daily-coding-summary.mjs`](../../scripts/daily-coding-summary.mjs) | Syncs the just-ended day's WakaTime data (after midnight, so the day is complete) then posts a Discord recap comparing it to the 30-day average |
| [wakatime-sync](wakatime-sync.yml) | 12:30 UK | [`wakatime-sync.py`](../../scripts/wakatime-sync.py) | Midday WakaTime sync so the coding dashboard shows the morning's hours during the day |
| [routine](routine.yml) | 07:00 UK | [`routine.mjs`](../../scripts/routine.mjs) | Posts the morning habit and streak checklist to Discord |
| [streak-reminder](streak-reminder.yml) | 08:00 UK | [`send-streak-reminder.mjs`](../../scripts/send-streak-reminder.mjs) | Reminds me on Discord which streaks are not yet logged today |
| [vault-expiry-check](vault-expiry-check.yml) | 08:00 UK | [`vault-expiry-check.mjs`](../../scripts/vault-expiry-check.mjs) | Alerts on Discord when vault or inventory items are near their expiry date |
| [recategorise](recategorise.yml) | 06:00 UK | [`recategorise.py`](../../scripts/recategorise.py) | Re-categorises "Software Engineering" catch-all applications with the AI (idempotent mop-up) |
| [medication-reminders](medication-reminders.yml) | every 30 min | [`medication-reminders.mjs`](../../scripts/medication-reminders.mjs) | Sends due medication reminders to Discord, email or SMS, de-duplicated against a dose log |
| [reminders](reminders.yml) | every 30 min | [`reminders.mjs`](../../scripts/reminders.mjs) | Sends one-off appointment and meeting reminders at their lead times, stamped so none repeats |
| [spotify-history](spotify-history.yml) | every 30 min | [`spotify-history.mjs`](../../scripts/spotify-history.mjs) | Records my Spotify plays into `listening_history` so the analytics build up real history |
| [job-scraper](job-scraper.yml) | 00:00 UTC (daily) | [`job-scraper.py`](../../scripts/job-scraper.py) | Scrapes graduate and internship sources and upserts them into the applications table |

## Repo automation

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [ci](ci.yml) | push, PR | Syntax-checks the Python and Node scripts so a broken change cannot land (no build step - the scripts are standalone) |
| [gitleaks](gitleaks.yml) | push, PR | Scans for hard-coded secrets |
| [automerge-dependabot](automerge-dependabot.yml) | PR | Enables squash auto-merge on Dependabot PRs and anything labelled `automerge` |
| [update-pr-branches](update-pr-branches.yml) | every 2h, push to main | Deletes merged PR branches the merge itself failed to clean up |

## UK time and the two-cron pattern

Every time-of-day job holds a fixed UK wall-clock time year-round. GitHub Actions is UTC only and does
not observe British Summer Time, so each such job fires from **two crons** - a GMT branch and a BST
branch one hour apart - and a **gate step** (`TZ=Europe/London date +%H`) lets the job run only at the
intended local hour, skipping the other branch. The two crons and the gate hour are noted in each
workflow.

Jobs that post a user-facing message (the coding recap, streak reminder and vault expiry check) also
claim the day in the shared `cron_runs` table via [`../../scripts/lib/uk-cron.mjs`](../../scripts/lib/uk-cron.mjs),
so a run that GitHub delayed into the target hour cannot double-post. A manual `workflow_dispatch` sets
`FORCE=1`, which bypasses both the gate and the idempotency claim so a test run always sends.

Two jobs deliberately opt out: the every-30-minute jobs are already `Europe/London`-aware in their own
scripts (with a window that absorbs cron jitter), and `job-scraper` stays on a single UTC midnight cron
because its cadence does not need a fixed local hour.

## Conventions

- One workflow per job, named for what it does; the workflow is a thin wrapper and the logic lives in the script.
- All runtime settings come from GitHub Actions secrets injected as environment variables; nothing configurable is committed.
- Third-party actions are pinned so a mutable tag cannot be silently updated.
