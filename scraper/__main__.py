"""Entry point for python -m scraper: the failure guard, the SCRAPER_AI_TEST self-test path and the run itself."""
import os
import sys

# The shared failure guard lives in scripts/lib and running as python -m scraper from the
# repo root does not put scripts/ on the path, so add it before the import.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from lib.report_failure import guard  # noqa: E402

from .runner import main  # noqa: E402

if __name__ == "__main__":
    with guard("job-scraper"):
        main()
