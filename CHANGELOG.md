# Changelog

All notable changes to these automation jobs are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## 2026-07-05

### Changed

- All scheduled jobs now hold a fixed UK wall-clock time year round. GitHub Actions is UTC only and does not observe British Summer Time, so each time-of-day job fires from two crons (a GMT branch and a BST branch one hour apart) and a gate step (`TZ=Europe/London date`) runs it only at the intended local hour. A shared `scripts/lib/uk-cron.mjs` provides the London-time helpers and a `cron_runs` idempotency claim. Retimed to true UK time: the streak reminder to 08:00, the vault expiry check to 08:00 and the nightly re-categorisation to 06:00, each with a `:10`/`:12` minute offset so a delayed run still lands inside the target hour
- Coding recap consolidated into one workflow at 00:30 Europe/London - it syncs WakaTime first (after midnight, so the previous day is complete) then posts the summary, which now reports the day that just ended rather than the UTC "today". This removes the timing race between the old separate 23:00 sync and 23:30 summary

### Added

- Midday WakaTime sync at 12:30 Europe/London so the coding dashboard reflects the morning's hours during the day, alongside the end-of-day sync that now runs inside the coding recap
- Cron idempotency guard - the jobs that post to Discord (coding recap, streak reminder, vault expiry) claim the day in the shared `cron_runs` table (portfolio migration 043) before sending, so a run that GitHub delayed into its target hour cannot double-post. A manual `workflow_dispatch` sets `FORCE=1` to bypass both the gate and the guard

## 2026-06-24

### Added

- Repository scaffold - gitleaks secret scanning, Dependabot for the action versions, a security policy, a code of conduct and a PolyForm Noncommercial licence
- Morning routine job - reads the day's habits and streaks from the database and posts a checklist to Discord at 07:00 Europe/London, with a British Summer Time guard so it fires at the right local hour year round
- Medication reminders job - sends due medication reminders to Discord, email or SMS every 30 minutes, de-duplicated against a dose log, firing at the right local time through BST and GMT
