# Changelog

All notable changes to these automation jobs are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## 2026-07-16

### Fixed

- A scraped row whose title carries no student signal at all resolves to the Jobs tab now, whatever it was stamped with before: the new resolve_type sits behind every source and the retype workflow, so "Networking Architect" and friends can never keep an Internship or Event label. The senior-title pattern also learns Sr, Architect and roman numeral grades, which is what let those rows keep hiding (#65)
- Rows that were inserted while the parser could not read their apply link heal themselves now: when a scrape meets a known company-and-role row that carries no URL, it fills the link in place, so the linkless Trackr rows from before the parser fix pick their links up on the next run (#65)
- The retype workflow also reports, without touching anything, the rows todays filters would no longer accept and the rows no scrape has seen in 14 days - the evidence base for a separately approved clean-up of listings that are gone from the boards (#65)
- Every job in the Discord alert links somewhere again. Trackr rows without an external apply link (the very rows the old parser used to mangle) posted as plain text once they parsed correctly; they now carry the Trackr company page as their link, fragment-tagged per programme so each URL stays unique for dedupe and in-place refreshes (#65)

### Added

- Thirteen live-verified companies join the scraper, leaning embedded and hardware for my placement hunt: Tenstorrent, Riverlane, Nothing, Helsing, Ocado Group and Anduril on Greenhouse; Cerebras, Cognition and Ramp on Ashby; Analog Devices, Micron, NXP and Marvell on Workday - four semiconductor majors the tracker never saw before. The priority list learns the embedded and semiconductor names, placement-year department names now count as student pipelines and Reed, Adzuna and Jooble each gain embedded, electronics and hardware placement searches alongside their untouched existing ones (#65)

### Fixed

- A full live sweep of every configured source (every ATS slug, every API, every browser career site) caught what had quietly died: Atlassian left Greenhouse, seven Ashby boards vanished, Perplexity renamed its slug and every single SmartRecruiters identifier returned an empty envelope, so that whole source had been contributing nothing - rebuilt around five tenants that verifiably return postings, Version 1 and Experian among them (#65)
- ARM's scraper works again and no longer needs a browser: the old Coveo search page 404s now, and their Radancy careers site answers plain JSON, so the roles come straight from that endpoint with the city read out of each job's path (#65)
- The Trackr scraper parses the current table correctly. A new My Status column had shifted every cell right, so rows without an external apply link stored the company name as the role; the company and programme columns are now read by header name, a row whose programme equals its company is skipped as the old failure mode and each row's type comes from its own title - the four category routes all serve the same 307-row table now, so one page load replaces four passes that each stamped rows with the wrong type (#65)
- The classification layer matches whole words now, because substring matching had been filing things in the wrong tabs everywhere: "replacement" and "outplacement" counted as placements, "Workshop Engineer" and networking-engineering roles looked like careers events, "Repair Technician" passed the tech check through the bare letters "ai" and a senior title could still win a placement label. Commercial roles (sales, account executive, business development, recruiting, marketing and friends) are rejected outright, which stops the noise priority companies washed in, and a senior title with no intern word always types as a full-time job. Every case comes straight from the verification runs and each one is now a test (#65)
- A dispatch-only one-off workflow moves the already-scraped rows to their correct tabs, recomputing each type from the row's own title with its current value as the fallback so titles without a real signal keep what they have. It lists the unrecoverable ghost rows whose role equals their company and deletes them only when explicitly asked; rows with a URL also self-heal on every normal scrape now that the update path writes the corrected type (#65)

- The scraper's existing-row pre-load now pages past PostgREST's 1000-row cap. A bare select silently stopped at the first 1000 rows once the table outgrew that, so every older listing looked brand new on every run: a wasted liveness check and AI enrichment call each, saved from duplication only by the unique-constraint fallback. The first packaged run printed "Found 999 existing applications" against a table several times that size, which is what gave it away (#69)

---

## 2026-07-15

### Changed

- The job scraper is a proper Python package now (`scraper/`, run as `python -m scraper`) instead of one 3,200-line script: one module per responsibility, one file per source with an ordered registry, the static company and keyword lists under `data/` and a RunContext object carrying the per-run state instead of module globals. Behaviour is identical from the database's point of view; a thin shim keeps the old script path working and the workflow, secrets and Healthchecks wiring are untouched (#64)
- The internship cycle cutoff moved up to January 2026: the 2025/26 season is over, so roles with a 2025 closing date are stale (#64)

### Added

- A pure-logic test suite (pytest) covering the relevance filters, location rules, date cutoffs and parsers, dedupe keys and the AI validator, with the cases lifted from the inline comments they protect (#64)
- The AI enrichment also derives the opening date and whether a CV is required, alongside the salary, work mode, closing date, visa sponsorship and cover letter it already extracted; an ATS-provided value still always wins (#64)
- A rate-limited AI provider is benched for the rest of the run, so every later extraction goes straight to the providers still answering instead of queueing behind a known-dead limit (#64)
- `SCRAPER_DRY_RUN=1` rehearses a full run, printing would-be inserts and updates instead of writing, and one shared HTTP session now carries the API sources' calls (#64)

---

## 2026-07-14

### Changed

- The job scraper now leans London without narrowing anything: Reed, Adzuna and Jooble each run London-targeted passes alongside their untouched UK-wide searches (Reed with a 20 mile Greater London radius) and the location filter recognises the London districts postings actually name, from Kings Cross to Hammersmith, so a London role is never dropped for being labelled by neighbourhood (#63)
- The daily analytics posts now carry the detail behind the counts. Fitness reports yesterday alone instead of a rolling week - each activity with its sport, distance, moving time, heart rate, calories and climb, plus day totals, or a rest-day note. Music adds total listening time, top artists and the top album. Posts split opens by post type and count finished reads. Applications list the roles applied to yesterday with company, category, work mode and location, break the live pipeline down by category and flag deadlines due in the next week, including openings not yet applied to (#61)
- Job health alerts moved to a dedicated `#automation-errors` Discord channel, so cron noise and website monitoring never mix in `#uptime` again; medication reminders also raise a Linear incident. Every Healthchecks check was re-tuned to the scheduler-era cadence at the same time - the reminder jobs now alarm within the hour of a real stall instead of four, and the daily jobs within two hours of their slot - safe because the windowed GitHub crons stay on as a second trigger path (#60)

---

## 2026-07-13

### Added

- A "dose failed to deliver" alert on the medication reminders job. When a dose is due and every configured channel fails, it now posts the reminder, its label, the time and the channels it tried to the private #errors channel, instead of only writing an id-only line to the public run log where nobody would see it. The dose stays unlogged so the next run retries delivery, and the alert surfaces the failure in the meantime (#54)
- An evening pass for the routine checklist and the streak reminder, at 20:00 UK. Each script now runs an am and a pm slot with its own once-a-day claim: the morning posts stay exactly as they were, and the evening run chases only what is still unlogged - habits and streaks left unticked, with time to save the chain - staying completely silent when everything is already done. A `slot` input on both workflows overrides the choice for manual runs, and the evening cron windows ride as GitHub backup alongside the scheduler (#58)

### Changed

- The coding recap and the daily analytics now post just after midnight instead of mid-morning - the recap from 00:30 UK, the analytics from 01:00 UK - so the day that just ended is summarised while it is fresh rather than after breakfast. The backup windows, gate steps and docs moved with them; the recap window opens at 00:30 so the final WakaTime heartbeats of the day settle before the sync reads them (#56)
- A manual run of a daily job no longer bypasses the once-a-day claim by default. The five daily workflows take a `force` tickbox instead of hard-wiring FORCE=1 on every dispatch, so a dispatch fired at the right time claims the day like a scheduled run and cannot double-post against the backup window, while ticking `force` still re-sends for testing. This clears the way for dispatch-driven scheduling (#56)

### Fixed

- The job-scraper docstring still said the scrape runs every two days; it has been daily since late June (#56)

---

## 2026-07-12

### Security

- Run logs now carry ids, counts and times only. The reminder, medication and vault jobs no longer print item detail, provider error logging is reduced to the status code and the scraper's Discord alert failure prints the error class alone, so public run logs stay free of personal detail. This is the standing pattern for every future job (#44)
- The job-scraper now reads its database key from `SUPABASE_SERVICE_ROLE_KEY` like every other job, retiring the mislabelled anon-key variable (#44)
- Workflow secrets are scoped to the script steps that need them instead of being visible to every step in the job (#44)
- Every first-party action is pinned to a full commit SHA that Dependabot keeps fresh and the gitleaks binary download is verified against its published checksum before it runs (#44)
- The Gemini key now travels in the `x-goog-api-key` header rather than the request URL, so no exception text can ever carry it (#51)

### Added

- A `pip` block in Dependabot so the scraper's Python dependencies get weekly update PRs like the Actions already do (#44)

### Fixed

- Hardened the scheduled jobs so a failed run can no longer pass for a success. The daily-day claim now throws on a database error instead of returning "already ran", so a blip surfaces through the #errors guard and the Healthchecks /fail ping rather than exiting quietly; daily-analytics releases its claim and exits non-zero when every section fails, so the day is retried instead of marked done with nothing posted, and it pages its applications query with the scraped rows filtered out server-side, so the counts cover every real application rather than a truncated first 1000 that the scraped rows had evicted; and spotify-history drops the local catch that was swallowing its failures, so a crash now reaches #errors in full through the shared guard (#52)

---

## 2026-07-11

### Added

- Full failure reporting on every job. When a job crashes it now posts the complete error, the stack trace plus a link to the exact Actions run, to the `#errors` Discord channel, through shared reporters (`scripts/lib/report-failure.mjs` for the Node jobs and `scripts/lib/report_failure.py` for the Python ones). Best-effort, so a webhook problem never masks the original error, which still goes to the run log. All eleven jobs are wired and `DISCORD_WEBHOOK_ERRORS` is passed to each workflow (#28)
- `STATUS.md`, a live status page with a Healthchecks badge for each job, its cadence and one line on what it does. The single README badge links to it so the README stays clean and the per-job breakdown is one click away (#28)

### Changed

- Each job now has its own dedicated Healthchecks check with its own cadence, grace and badge, tagged so they can be pulled as a group. The high-frequency reminder jobs use a period check rather than a strict per-slot schedule so a single late or dropped GitHub Actions run does not false-alarm: reminders and medication-reminders alert after 60 minutes of silence, Spotify history after three hours, while the windowed and daily jobs keep their exact cron schedule. Down and late alerts route to the `#uptime` Discord channel (#28)

---

## 2026-07-09

### Added

- Healthchecks.io monitoring on every scheduled job. A shared composite action (`.github/actions/healthcheck`) pings `hc-ping.com/<key>/<slug>` on start, success and fail, one slug per job, so a job that stops running, fails or hangs raises an alert instead of failing silently for days. Guarded on the `HEALTHCHECK_PING_KEY` secret: with no key set every ping is a no-op and the jobs run unchanged. The job-scraper reports success only when both its parallel jobs succeed (#16)

---

## 2026-07-08

### Added

- Daily analytics summary - a new job posts a per-page summary (Applications, Posts, Fitness, Music) to each dashboard analytics Discord channel for the day that just ended, each channel optional and skipped if its webhook is unset (#15)

### Changed

- Reliable scheduling for every daily job. GitHub Actions drops scheduled runs, worst at the top of the hour, so each daily job now fires every 30 minutes across a morning window at off-peak minutes rather than from one slot, gates to its target UK hour and claims the day in `cron_runs` so it acts exactly once whenever a run lands. The routine checklist and daily analytics join the coding recap, streak reminder and vault check in claiming the day. WakaTime sync runs every 3 hours (idempotent), and the job-scraper fires from two off-peak tries (#15)

### Fixed

- Medication reminders catch up on any dose that came due while runs were being dropped, rather than only firing inside a fixed window, so a delayed run still sends and the per-dose dedup keeps it from repeating (#15)

---

## 2026-07-05

### Added

- Spotify history job - a 30-minute job records my recently-played tracks into the `listening_history` table, de-duplicated by `played_at`, so the analytics can show real play counts and active hours (the Spotify API alone only returns top-N and the last 50 plays). It skips cleanly until the Spotify secrets are set (#5)
- Scraper failure alert - a notify-failure job runs when either scraper job fails and posts the run link to the `#errors` Discord channel, so a broken scrape surfaces at once instead of days later (#4)
- GitHub Models added as a fourth AI fallback for the scraper and re-categorisation chain (Groq, then Gemini, then OpenRouter, then GitHub Models), so a Groq rate limit no longer stalls a run; whatever a single run cannot categorise is retried by the nightly schedule. The prompt also routes robotics roles to Embedded and PCB roles to Hardware
- Midday WakaTime sync at 12:30 Europe/London so the coding stats reflect the morning's hours during the day, alongside the end-of-day sync that now runs inside the coding recap
- Cron idempotency guard - the jobs that post to Discord (coding recap, streak reminder, vault expiry) claim the day in the shared `cron_runs` table (portfolio migration 043) before sending, so a run that GitHub delayed into its target hour cannot double-post. A manual `workflow_dispatch` sets `FORCE=1` to bypass both the gate and the guard
- Documentation - a README for the workflows folder (every workflow, its schedule and the UK-time two-cron pattern), a README for the scripts folder (each script and the secrets it needs), a root `.env.example` listing every secret name with placeholders, and a workflow guide in `.github` describing how changes are made here (#4, #6, #7)

### Changed

- All scheduled jobs now hold a fixed UK wall-clock time year round. GitHub Actions is UTC only and does not observe British Summer Time, so each time-of-day job fires from two crons (a GMT branch and a BST branch one hour apart) and a gate step (`TZ=Europe/London date`) runs it only at the intended local hour. A shared `scripts/lib/uk-cron.mjs` provides the London-time helpers and a `cron_runs` idempotency claim. Retimed to true UK time: the streak reminder to 08:00, the vault expiry check to 08:00 and the nightly re-categorisation to 06:00, each with a `:10`/`:12` minute offset so a delayed run still lands inside the target hour (#3)
- Coding recap consolidated into one workflow at 00:30 Europe/London - it syncs WakaTime first (after midnight, so the previous day is complete) then posts the summary, which now reports the day that just ended rather than the UTC "today". This removes the timing race between the old separate 23:00 sync and 23:30 summary (#3)

### Fixed

- The GitHub Models secret is read as `GH_MODELS_TOKEN`, because GitHub Actions reserves the `GITHUB_` prefix for its own secrets (#2)

## 2026-07-04

### Added

- Reminders delivery job - sends one-off appointment, meeting and general reminders from the `reminders` table (portfolio migration 042) every 30 minutes. A reminder can carry several lead times and each fires once when its moment arrives, to any of Discord, email and SMS, recorded in `sent_leads` so none repeats. Reuses the Resend, Discord webhook and Twilio setup from the medication reminders job, and a `workflow_dispatch` with `test_email` or `test_to` sends one test message (#1)

### Changed

- The re-categorisation now runs nightly to mop up any "Software Engineering" catch-all rows the daily scrape adds. It is idempotent, so it changes nothing once everything is already sorted, and a scheduled run applies for real (dry-run only defaults on the manual trigger)

### Fixed

- The daily re-scrape no longer reverts the AI categories and enrichment. A refresh had rebuilt `category` from the regex and blanked salary and work mode, because the AI enrichment only runs for brand-new rows, so it washed out the categorisation every day. The refresh now leaves `category` untouched and never overwrites an existing value with an empty one

## 2026-06-25

### Added

- AI field extraction and categorisation for the job scraper - a role that carries a description is sent to an LLM (Groq first, then Gemini, then OpenRouter) that picks the correct category tab and fills any missing salary, work mode, deadline, visa sponsorship or cover letter. It only fills empty scraper-owned fields, keeps the reliable company-based FAANG+ and Quant categories from the regex and never touches user-owned columns like status or notes. A `workflow_dispatch` `ai_test` input runs a quick self-test
- One-off AI re-categorisation backfill - re-sorts existing scraped applications with the same Groq to Gemini to OpenRouter chain, from title and company since old rows have no stored description. It updates only the `category` column and defaults to a dry run (the old regex put 74% of roles in Software Engineering and never produced the Hardware or Startups tabs)

### Changed

- The job scraper runs daily at 00:00 UTC instead of every two days, now that it is on the free public repo. Adzuna stays well under its 1000-request monthly trial limit at roughly 420 a month
- The backfill re-categorises only the "Software Engineering" catch-all and leaves any already-sorted row untouched, so a correct category can never change; batch size widened to 40 for fewer AI calls per run

### Fixed

- The AI fallback uses `gemini-2.5-flash`. The retired `gemini-1.5-flash` endpoint returned 404, so when Groq hit its rate limit the fallback was dead. The backfill also waits longer between batches to stay within the free-tier rate limits

## 2026-06-24

### Added

- Repository scaffold - gitleaks secret scanning, Dependabot for the action versions, a security policy, a code of conduct and a PolyForm Noncommercial licence
- Morning routine job - reads the day's habits and streaks from the database and posts a checklist to Discord at 07:00 Europe/London, with a British Summer Time guard so it fires at the right local hour year round
- Medication reminders job - sends due medication reminders every 30 minutes, de-duplicated against a dose log and firing at the right local time through BST and GMT. A reminder can go to Discord, email and SMS at once via a channels array (email through Resend, SMS through Twilio), and a `workflow_dispatch` with `TEST_TO` or `TEST_EMAIL` sends one test message
- Migrated the scheduled data jobs from the portfolio repo - the WakaTime sync, the daily coding summary, the morning streak reminder, the vault and inventory expiry check and the job scraper, each a workflow wrapping a self-contained script. The three Node scripts were rewritten dependency-free to match the routine and medication style, and the Python jobs share one requirements file
- Repo hygiene workflows - a CI compile-check (`python compileall` and `node --check`) on every push and pull request, Dependabot auto-merge once checks pass, and a scheduled Repo maintenance job that deletes merged branches the merge did not clean up

### Fixed

- Strip whitespace from the credential environment variables in the Python jobs - a trailing newline in the `SUPABASE_URL` secret broke httpx (it rejects a newline in a URL, while the Node fetch parser silently stripped it)
