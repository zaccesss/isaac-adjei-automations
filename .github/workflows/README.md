# Workflows

Every job is a GitHub Actions workflow here, wrapping a script in [`../../scripts`](../../scripts).
The scheduled jobs are split into two groups: the scheduled jobs that do the actual work, and the
repo-automation workflows that keep the repository itself healthy.

## Scheduled jobs

Every scheduled job fires from a frequent window rather than a single slot, because GitHub Actions cron
delays and drops runs (worst at the top of the hour). The job then gates itself to the intended UK hour
and claims the day so it acts exactly once. See [UK time and the windowed schedule](#uk-time-and-the-windowed-schedule).

| Workflow | Schedule (UK) | Script | Purpose |
| --- | --- | --- | --- |
| [daily-coding-summary](daily-coding-summary.yml) | once, 00:30-03:00 window | [`wakatime-sync.py`](../../scripts/wakatime-sync.py) then [`daily-coding-summary.mjs`](../../scripts/daily-coding-summary.mjs) | Syncs the just-ended day's WakaTime data then posts a Discord recap comparing it to the 30-day average |
| [wakatime-sync](wakatime-sync.yml) | every 3 hours | [`wakatime-sync.py`](../../scripts/wakatime-sync.py) | Keeps the coding stats fresh through the day (idempotent, so a dropped run is harmless) |
| [routine](routine.yml) | twice: 07:00-09:00 and a 20:00-22:00 evening pass | [`routine.mjs`](../../scripts/routine.mjs) | Posts the morning habit and streak checklist to Discord; the evening pass chases only what is still unlogged and stays silent when the day is done |
| [streak-reminder](streak-reminder.yml) | twice: 08:00-10:00 and a 20:00-22:00 evening pass | [`send-streak-reminder.mjs`](../../scripts/send-streak-reminder.mjs) | Reminds me on Discord which streaks are not yet logged today; the evening pass posts only while something is still unlogged |
| [vault-expiry-check](vault-expiry-check.yml) | once, 08:00-10:00 window | [`vault-expiry-check.mjs`](../../scripts/vault-expiry-check.mjs) | Alerts on Discord when vault or inventory items are near their expiry date |
| [daily-analytics](daily-analytics.yml) | once, 01:00-04:00 window | [`daily-analytics.mjs`](../../scripts/daily-analytics.mjs) | Posts a per-page analytics summary (Applications, Posts, Fitness, Music) to each dashboard analytics channel |
| [recategorise](recategorise.yml) | once, 06:00-09:00 window | [`recategorise.py`](../../scripts/recategorise.py) | Re-categorises "Software Engineering" catch-all applications with the AI (idempotent mop-up) |
| [medication-reminders](medication-reminders.yml) | every 30 min | [`medication-reminders.mjs`](../../scripts/medication-reminders.mjs) | Sends due medication reminders to Discord, email or SMS, de-duplicated against a dose log |
| [reminders](reminders.yml) | every 30 min | [`reminders.mjs`](../../scripts/reminders.mjs) | Sends one-off appointment and meeting reminders at their lead times, stamped so none repeats |
| [spotify-history](spotify-history.yml) | every 30 min | [`spotify-history.mjs`](../../scripts/spotify-history.mjs) | Records my Spotify plays into `listening_history` so the analytics build up real history |
| [job-scraper](job-scraper.yml) | 01:23 and 04:41 UTC (two tries) | [`scraper/`](../../scraper/) (`python -m scraper`) | Scrapes graduate and internship sources and upserts them into the applications table |

## Repo automation

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [ci](ci.yml) | push, PR | Syntax-checks the Python and Node scripts so a broken change cannot land (no build step - the scripts are standalone) |
| [gitleaks](gitleaks.yml) | push, PR | Scans for hard-coded secrets |

Dependabot PR auto-merge and merged-branch cleanup are handled centrally by repo-ops, so this repo carries no auto-merge or branch-maintenance workflow of its own.

## UK time and the windowed schedule

Every time-of-day job holds a fixed UK wall-clock time year-round. GitHub Actions is UTC only, does not
observe British Summer Time and (worse) delays or drops scheduled runs, especially at the top of the
hour. So instead of one fragile slot, each daily job fires **every 30 minutes across a window** that
covers its target hour in both GMT and BST. A **gate** (either a workflow step running
`TZ=Europe/London date +%H` or the same check in the script) lets it act only once the local hour has
reached the target, and it **claims the day** in the shared `cron_runs` table via
[`../../scripts/lib/uk-cron.mjs`](../../scripts/lib/uk-cron.mjs) so whichever run lands first does the work
and later runs in the window skip. A manual `workflow_dispatch` runs straight away (the gates let a
dispatch through) but still claims the day, so a dispatch cannot double-post against the window; tick the
`force` input to bypass the gate and the claim when a test run should always act.

The every-30-minute jobs (medication, reminders, Spotify) do not gate to an hour: they run all day and
de-duplicate their own work. `job-scraper` fires from two off-peak UTC crons (a dropped one does not cost
a day, and the scrape upserts so running twice is harmless).

## Monitoring

Every scheduled job is watched by [Healthchecks.io](https://healthchecks.io). A shared composite action
[`../actions/healthcheck`](../actions/healthcheck/action.yml) pings `hc-ping.com/<key>/<slug>` on **start**,
**success** and **fail**, with one slug per job (for example `routine`, `daily-analytics`, `job-scraper`).
A job that stops running, fails or hangs then shows as down or late on the status page and alerts the
`#automation-errors` Discord channel, instead of failing silently for days. The ping is guarded on the
`HEALTHCHECK_PING_KEY` secret, so with no key set it is a no-op and the jobs run unchanged. `job-scraper`
reports success only when both its parallel jobs succeed.

The overall status badge is in the [root README](../../README.md), and the down/late/fail alert is wired
in the Healthchecks.io project itself (Integrations, then Discord) rather than in this repo, so the alert
routing stays out of the code. Only the read-only Healthchecks API key is used to read check status.

## Conventions

- One workflow per job, named for what it does; the workflow is a thin wrapper and the logic lives in the script.
- All runtime settings come from GitHub Actions secrets injected as environment variables; nothing configurable is committed.
- Third-party actions are pinned so a mutable tag cannot be silently updated.
