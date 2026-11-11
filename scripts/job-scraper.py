# thin shim kept at the old path: the scraper lives in the jobs/scraper package now and
# runs as python -m scraper with jobs/ on the path. Anything still invoking this path gets
# the identical run.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs"))

from scraper.__main__ import entry  # noqa: E402

if __name__ == "__main__":
    from lib.report_failure import guard

    with guard("job-scraper"):
        entry()
