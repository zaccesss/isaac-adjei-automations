"""The wall-clock budget check between companies and sources."""
import time


def over_budget(ctx) -> bool:
    return time.time() - ctx.run_start > ctx.budget_seconds
