"""Plain-text description detectors: visa sponsorship and cover letter mentions."""

import re

# ─── URL CHECKS AND LOCATION ENRICHMENT ─────────────────────────────────────

def detect_sponsors_visa(text: str) -> "bool | None":
    """Scan job description text for visa sponsorship signals.

    Returns True if the company explicitly sponsors, False if they state they
    cannot/do not, or None when the description is silent on the topic.
    """
    if not text:
        return None
    t = text.lower()
    no_signals = [
        "cannot sponsor", "unable to sponsor", "not able to sponsor",
        "do not offer visa", "no visa sponsorship", "sponsorship is not available",
        "cannot provide visa", "right to work in the uk",
        "right to work in the united kingdom",
        "you must have the right to work",
        "must have the right to work",
        "eligible to work in the uk",
        "eligible to work in the united kingdom",
        "must be eligible to work",
        "must have existing right",
        "will not sponsor", "won't sponsor", "won't be able to provide sponsorship",
        "does not provide sponsorship", "not currently able to sponsor",
        "cannot support a visa", "unable to provide visa",
    ]
    for s in no_signals:
        if s in t:
            return False
    yes_signals = [
        "visa sponsorship is available", "we sponsor visas",
        "visa sponsorship available", "we provide visa sponsorship",
        "tier 2 visa", "skilled worker visa sponsorship",
        "can sponsor your visa", "sponsorship is available",
        "we are able to sponsor",
    ]
    for s in yes_signals:
        if s in t:
            return True
    return None


def detect_cover_letter_required(text: str) -> "bool | None":
    """Return True if the description explicitly mentions a cover letter."""
    if not text:
        return None
    return True if "cover letter" in text.lower() else None


def _strip_html(html: str) -> str:
    """Remove HTML tags to get plain text for description scanning."""
    return re.sub(r"<[^>]+>", " ", html or "")
