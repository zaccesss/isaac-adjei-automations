"""Cycle cutoffs, the 14 day grace window and the source date parsers."""

from datetime import datetime, timedelta

# Internship cycle cutoff: Jan 2025 start of 2025/26 recruiting season.
CYCLE_CUTOFF = datetime(2026, 1, 1)
# Full-time job cutoff: Jan 2026 - only include recently posted roles.
JOB_CUTOFF = datetime(2026, 1, 1)


def is_date_relevant(closing_date_str: "str | None", cutoff: "datetime | None" = None) -> bool:
    """True if the role's closing date is within the expected cycle and not expired."""
    if not closing_date_str:
        return True  # no deadline = include (unknown)
    try:
        d = datetime.strptime(closing_date_str, "%Y-%m-%d")
        # I keep roles whose deadline passed within the last 14 days so a freshly
        # closed posting still shows (late applications are sometimes accepted)
        # rather than dropping it the instant the date ticks over.
        grace = datetime.now() - timedelta(days=14)
        effective_cutoff = cutoff if cutoff is not None else CYCLE_CUTOFF
        return d >= effective_cutoff and d >= grace
    except ValueError:
        return True


def _parse_greenhouse_date(dt_str: "str | None") -> "str | None":
    """Convert a Greenhouse ISO timestamp to a plain YYYY-MM-DD string."""
    if not dt_str:
        return None
    try:
        return dt_str[:10]  # "2026-01-15T08:12:57-04:00" → "2026-01-15"
    except Exception:
        return None


def _parse_trackr_date(s: "str | None") -> "str | None":
    """Parse a Trackr date cell ('21 May 26', '21 May 2026', '21/05/2026') to
    YYYY-MM-DD, or None for blanks and rolling/TBC placeholders."""
    if not s:
        return None
    s = s.strip()
    if not s or s.lower() in ("-", "tbc", "tbd", "n/a", "na", "rolling", "asap", "open"):
        return None
    for fmt in ("%d %b %y", "%d %b %Y", "%d/%m/%Y", "%d/%m/%y", "%d %B %Y", "%d %B %y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None
