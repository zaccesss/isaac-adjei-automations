"""Every environment read in one place: Supabase, mode, budgets, AI keys and the board API keys.

Everything reads via .get so the pure modules stay importable without any environment
(the tests need that); RunContext.create() enforces the database pair before a real
run, failing as early and loudly as the old module-level client creation did.
"""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# "api" | "browser" | "all" - the GitHub Actions workflow runs two parallel jobs that
# split the work without running each other's scrapers.
SCRAPER_MODE = os.environ.get("SCRAPER_MODE", "all")

# hard wall-clock budget so the script exits cleanly before GitHub Actions kills the
# job. The repo is public, so Actions minutes are unlimited; the default 110 min sits
# a few minutes under the 120 min job timeout so the run still exits cleanly. A higher
# budget matters most for the browser/Trackr job, which carries the internships.
BUDGET_SECONDS = int(os.environ.get("SCRAPER_BUDGET_MIN", "110")) * 60

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
AI_BUDGET = int(os.environ.get("SCRAPER_AI_BUDGET", "150"))

REED_API_KEY = os.environ.get("REED_API_KEY", "")
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
JOOBLE_API_KEY = os.environ.get("JOOBLE_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# SCRAPER_DRY_RUN=1 rehearses a run: everything scrapes and filters as normal but the
# database writes and the Discord alert are printed instead of sent.
DRY_RUN = os.environ.get("SCRAPER_DRY_RUN", "").strip() == "1"

# the most new rows each newer source may insert in one run. These sources reach
# well beyond the student boards, so a cap stops one noisy feed from flooding the
# dashboard; rows it already holds are still refreshed once a cap is reached. A
# company named here also gets the stricter discipline and UK checks in
# filters.passes_new_source_guard.
MAX_NEW_PER_SOURCE = {
    "Gradcracker EE": 30,
    "Thales": 15,
    "Arm": 10,
    "Imagination Technologies": 5,
    "Raspberry Pi": 5,
    # UKESF partner companies with a public feed, added November 2026
    "Collins Aerospace": 10,
    "Teledyne": 10,
    "Sensata": 5,
    "Spectrum Control": 5,
    "Infinitesima": 5,
    "Codasip": 5,
    "EnSilica": 5,
    "Cosmic Semiconductor": 5,
    "Infineon": 10,
    "Qualcomm": 10,
    "Blighter": 5,
    "CML Micro": 5,
    "Viper Innovations": 5,
    "MK Test Systems": 5,
}
