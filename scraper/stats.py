"""Per-source stat recording and the source-stats.md summary writer."""


# I accumulate one row per source so main() can write a summary table at the end.
_source_stats: list[dict] = []


def _record_stat(source: str, rows: int, note: str = "") -> None:
    # I append to the module-level list rather than returning so every scraper
    # function can call this without needing to thread a return value through.
    _source_stats.append({"source": source, "rows": rows, "note": note})
