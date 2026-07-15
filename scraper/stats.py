"""Per-source stat recording and the source-stats.md summary writer."""


def record_stat(ctx, source: str, rows: int, note: str = "") -> None:
    # I append to the run context rather than returning so every scraper function
    # can call this without needing to thread a return value through.
    ctx.source_stats.append({"source": source, "rows": rows, "note": note})


def write_summary(ctx) -> None:
    # I write a Markdown summary table to source-stats.md so the workflow can cat it
    # into $GITHUB_STEP_SUMMARY and make failures visible at a glance. The file is
    # written regardless of whether GITHUB_STEP_SUMMARY is set so it can be
    # inspected locally too.
    if not ctx.source_stats:
        return
    lines = [
        "| Source | Rows added | Note |",
        "|---|---|---|",
    ]
    for stat in ctx.source_stats:
        # I coerce None note to empty string for cleaner table output.
        note = stat.get("note") or ""
        lines.append(f"| {stat['source']} | {stat['rows']} | {note} |")
    with open("source-stats.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")
