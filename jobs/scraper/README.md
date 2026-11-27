# scraper

A daily data sync, run as a package by its workflow. It only inserts and updates
rows; it never deletes anything.

## Running

From the repo root, with `jobs` on the Python path, which is what the workflow does:

```sh
export PYTHONPATH=jobs
python -m scraper
python -m pytest tests/   # the pure-logic tests (they set their own path)
```

Every setting comes from the environment. A missing optional setting skips its feature; nothing crashes.
