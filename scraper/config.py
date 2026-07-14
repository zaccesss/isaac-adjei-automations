"""Every environment read in one place: Supabase, mode, budgets, AI keys and the board API keys."""

import os

# I allow the GitHub Actions workflow to pass SCRAPER_MODE=api or
# SCRAPER_MODE=browser so two parallel jobs can split the work without
# running each other's scrapers.
SCRAPER_MODE = os.environ.get("SCRAPER_MODE", "all")  # "api" | "browser" | "all"
