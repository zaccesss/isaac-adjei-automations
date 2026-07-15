"""RunContext carries the per-run state that used to live in module globals."""
import time
from dataclasses import dataclass, field

from . import config


@dataclass
class RunContext:
    """Everything one scrape run mutates, threaded through the call tree.

    seen_urls collects every URL seen this run for the end-of-run freshness stamp;
    existing_urls holds the URLs already in the database at load time so insert_job
    knows whether to insert a new row or refresh the scraper-owned fields of an
    existing one; new_jobs collects the newly inserted student roles for the
    end-of-run Discord alert; ai_calls counts enrichment calls against AI_BUDGET.
    """

    supabase: object
    existing_keys: set = field(default_factory=set)
    existing_urls: set = field(default_factory=set)
    seen_urls: set = field(default_factory=set)
    new_jobs: list = field(default_factory=list)
    source_stats: list = field(default_factory=list)
    ai_calls: int = 0
    run_start: float = field(default_factory=time.time)
    budget_seconds: int = field(default_factory=lambda: config.BUDGET_SECONDS)

    @classmethod
    def create(cls) -> "RunContext":
        # A real run needs the database. Fail as early and loudly as the old
        # module-level client creation did when the pair was missing.
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise KeyError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        from supabase import create_client

        # The client is shared across all scraper functions rather than
        # re-initialising a new connection for every company.
        return cls(supabase=create_client(config.SUPABASE_URL, config.SUPABASE_KEY))

    @classmethod
    def bare(cls) -> "RunContext":
        # For the SCRAPER_AI_TEST self-test path only: no database is touched.
        return cls(supabase=None)
