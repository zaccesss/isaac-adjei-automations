# scraper

The job scraper as a package: 20+ sources of student tech roles scraped daily and
upserted into the Supabase `applications` table. It only ever inserts and updates,
never deletes, and never touches user-owned columns (status, notes, starred,
applied date) on an existing row.

## Layout

| Module | What lives there |
|---|---|
| `__main__.py` | Entry point: the failure guard, the `SCRAPER_AI_TEST` self-test and the run |
| `config.py` | Every environment read in one place |
| `context.py` | `RunContext`, the per-run state threaded through every call |
| `runner.py` | Orchestrates the sources in their long-standing order |
| `budget.py` | The wall-clock budget check |
| `http.py` | Browser headers, the shared session and the URL liveness check |
| `models.py` | The `Job` shape the database layer consumes |
| `filters.py` | Student-role detection, type inference and category detection |
| `locations.py` | Location vocabulary and the UK and Europe filter (London leaning) |
| `dates.py` | Season cutoffs, the 14 day grace window and the source date parsers |
| `db.py` | Dedupe keys, existing-row loading, the insert-or-refresh upsert, the freshness stamp |
| `ai.py` | Optional field extraction: Groq, Gemini, OpenRouter then GitHub Models, with rate-limited providers benched per run |
| `detect.py` | Plain-text detectors: visa sponsorship and cover letter mentions |
| `notify.py` | The end-of-run Discord alert for new student roles |
| `stats.py` | Per-source stats and the `source-stats.md` summary |
| `data/` | Static lists: ATS company slugs, priority companies, keyword vocabularies |
| `sources/` | One file per scraper plus the ordered registry in `__init__.py` |

## Running

```sh
python -m scraper                 # full run (needs the env below)
SCRAPER_MODE=api python -m scraper       # API sources only
SCRAPER_MODE=browser python -m scraper   # Playwright sources only
SCRAPER_DRY_RUN=1 python -m scraper      # rehearse: print would-be writes, touch nothing
SCRAPER_AI_TEST=1 python -m scraper      # AI extraction self-test, no scrape
python -m pytest tests/                  # the pure-logic test suite
```

`scripts/job-scraper.py` remains as a thin shim running the identical entry point.

## Environment

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are required for a real run.
Optional: `SCRAPER_MODE`, `SCRAPER_BUDGET_MIN`, `SCRAPER_DRY_RUN`, `SCRAPER_AI_TEST`,
`SCRAPER_AI_BUDGET`, the AI keys (`GROQ_API_KEY`, `GOOGLE_AI_API_KEY`,
`OPENROUTER_API_KEY`, `GH_MODELS_TOKEN`), the board keys (`REED_API_KEY`,
`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`) and `DISCORD_WEBHOOK_URL` for
the new-roles alert. A missing optional key skips its feature; nothing crashes.
