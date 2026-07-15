"""Entry point for python -m scraper: the failure guard, the SCRAPER_AI_TEST self-test path and the run itself."""
import os
import sys

# The shared failure guard lives in scripts/lib and running as python -m scraper from
# the repo root does not put scripts/ on the path, so add it before the import.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from lib.report_failure import guard  # noqa: E402

from . import config  # noqa: E402
from .ai import ai_extract  # noqa: E402
from .context import RunContext  # noqa: E402
from .runner import main  # noqa: E402


def entry():
    # Quick AI self-test: SCRAPER_AI_TEST runs the extractor on a sample advert and
    # exits, so I can confirm the providers and JSON parsing work without a full
    # scrape and without touching the database.
    if os.environ.get("SCRAPER_AI_TEST", "").strip():
        sample = (
            "Graduate Embedded Software Engineer at a London fintech startup. We design custom FPGA "
            "and firmware for low-latency trading hardware in C++ and Rust. Salary GBP 50,000 to "
            "60,000. Hybrid, three days in the office. We sponsor Skilled Worker visas for strong "
            "candidates. A cover letter is required. Apply by 2026-09-30."
        )
        print("AI keys present -> groq:", bool(config.GROQ_API_KEY), "gemini:", bool(config.GOOGLE_AI_API_KEY), "openrouter:", bool(config.OPENROUTER_API_KEY))
        print("AI test result:", ai_extract(RunContext.bare(), sample, "Graduate Embedded Software Engineer", "FinTech Startup"))
        return
    main()


if __name__ == "__main__":
    with guard("job-scraper"):
        entry()
