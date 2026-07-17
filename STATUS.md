# Status

Live health of every scheduled job, monitored by [Healthchecks.io](https://healthchecks.io). Each job
pings its own check on start, success and failure; a check goes **down** if a job stops pinging past its
grace window; that alert lands in the `#automation-errors` Discord channel (medication reminders also
raise a Linear incident). Self-reported errors (a job that runs but throws) post the full trace to
`#errors`.

Overall: ![automations](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/Qr8d_Bxl/automations.svg)

## Reminders and health

| Job | Status | Cadence | What it does |
|---|---|---|---|
| Reminders | ![reminders](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/PBHg40DK/reminders.svg) | every 30 min | Fires one-off appointment and meeting reminders over Discord, email and SMS |
| Medication reminders | ![medication-reminders](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/LlvuveB0/medication-reminders.svg) | every 30 min | Sends due medication doses over Discord, email and SMS, logging each so none repeats |
| Routine checklist | ![routine](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/4B5WCt1O/routine.svg) | 07-09 + 20-22 UK | Posts the morning habit and streak checklist to `#routine`, then an evening pass of what is still unlogged |
| Streak reminder | ![streak-reminder](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/mRKs2Rhy/streak-reminder.svg) | 08-10 + 20-22 UK | Nudges me to keep the coding and study streaks alive, morning and evening |
| Vault expiry check | ![vault-expiry-check](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/zwhJK1gB/vault-expiry-check.svg) | 07-10 UK | Warns about vault credentials that are about to expire |

## Coding and analytics

| Job | Status | Cadence | What it does |
|---|---|---|---|
| Daily coding summary | ![daily-coding-summary](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/ANzypoxl/daily-coding-summary.svg) | 00:30-03 UK | Posts the WakaTime coding summary to `#coding` |
| Daily analytics | ![daily-analytics](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/gwYAU-IS/daily-analytics.svg) | 01-04 UK | Posts blog, fitness, applications and music digests to their channels |
| WakaTime sync | ![wakatime-sync](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/yd__upOn/wakatime-sync.svg) | every 3 hours | Syncs WakaTime coding time into the database |

## Data and jobs

| Job | Status | Cadence | What it does |
|---|---|---|---|
| Job scraper | ![job-scraper](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/osSSm2dX/job-scraper.svg) | daily, two off-peak tries | Scrapes the job boards and career sites and posts new roles to `#jobs` |
| Spotify history | ![spotify-history](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/VYd-foem/spotify-history.svg) | every 30 min | Records my Spotify plays into `listening_history` for the analytics pages |
| Recategorise | ![recategorise](https://healthchecks.io/badge/40ef3b24-9e3e-460f-b735-7f71dd0bc0e1/rpqZYXYy/recategorise.svg) | 05-08 UK | Re-tags scraped applications, idempotently |

---

Schedules are UTC in the workflow files; the windowed jobs additionally gate on the Europe/London hour
so they land at the right local time year round. The reminder jobs use a period check (at least one ping
an hour, 15 minutes grace) rather than a strict per-slot schedule, because they run every 30 minutes and
a single late or skipped GitHub Actions run should not raise a false alarm.
