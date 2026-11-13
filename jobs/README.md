# Jobs

The larger jobs, each a Python package in a folder of its own. A job that fits in one file is a script in
[`scripts`](../scripts/README.md) instead.

| Job | What it does | Started by |
| --- | --- | --- |
| [`scraper`](scraper/README.md) | Reads 20+ sources of student tech roles each day and upserts them into the Supabase `applications` table | [`job-scraper.yml`](../.github/workflows/job-scraper.yml), by dispatch only |

## How a job here runs

This folder goes on the Python path and a job runs by its module name. From the repo root:

```bash
export PYTHONPATH=jobs
python -m scraper
```

The workflow sets `PYTHONPATH` the same way. The scripts that import a job and the tests add this folder to the
path themselves. Each job's own README lists its modes and the environment it needs.
