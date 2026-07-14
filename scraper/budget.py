"""The wall-clock budget check between companies and sources."""

import os
import time

# Hard wall-clock budget so the script exits cleanly before GitHub Actions kills the job. The repo is
# public, so Actions minutes are unlimited and the old 17-22 min cap (which got runs cancelled before
# they could finish and write their summary) is lifted. SCRAPER_BUDGET_MIN lets each workflow job tune
# it; the default 110 min sits a few minutes under the 120 min job timeout so the run still exits
# cleanly. A higher budget matters most for the browser/Trackr job, which carries the internships.
_BUDGET_SECONDS = int(os.environ.get("SCRAPER_BUDGET_MIN", "110")) * 60
_RUN_START = time.time()

def _over_budget() -> bool:
    return time.time() - _RUN_START > _BUDGET_SECONDS
