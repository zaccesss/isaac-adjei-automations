"""The shared role rules: which kind of student role a title names and whether it is in the cycle.

These mirror Vitafolio's App\\Support\\Jobs\\RoleType term for term, so the dashboard and the public
Jobs page sort a role the same way. Every term matches whole words only: plain substring checks let
"internal" count as an internship, "replacement" as a placement and "Senior Graduate Recruiter" as
a graduate role. Change a term in both places.
"""
import re
from datetime import datetime, timezone

PLACEMENT = [
    "placement", "placements", "placement year", "year in industry", "industrial placement", "industrial year",
    "sandwich year", "sandwich placement", "12 month placement", "12-month placement", "year-long placement",
    "year long placement", "work placement",
]
INSIGHT = [
    "spring week", "spring insight", "insight week", "insight day", "insight days", "insight programme",
    "insight program", "insight experience", "insight event", "insight evening", "insights summer school",
    "insight summer school", "spring programme", "spring program", "discovery programme", "discovery day",
    "discovery week", "spring intern", "spring internship",
]
GRADUATE = [
    "graduate", "graduates", "grad", "graduate scheme", "graduate programme", "graduate program", "grad scheme",
    "new grad", "entry level", "entry-level", "early careers", "early career", "early talent", "analyst programme",
    "analyst program", "associate programme", "associate program", "development programme", "development program",
    "rotational programme", "rotational program", "graduate rotational",
]
INTERNSHIP = [
    "intern", "interns", "internship", "internships", "summer intern", "off-cycle intern", "co-op",
    "student researcher", "undergraduate researcher", "vacation scheme", "summer analyst", "off-cycle analyst",
    "off cycle analyst", "off-cycle internship", "summer associate",
]

# staff who run these schemes and senior roles that mention them are never student roles
_STAFF = re.compile(
    r"\b(senior|sr\.?|staff|lead|principal|head of|director|manager|vp|vice president|architect|recruiter|"
    r"recruitment|talent acquisition|coordinator|co-ordinator|officer|adviser|advisor|lecturer|supervisor|"
    r"mentor|ii|iii|iv)\b",
    re.IGNORECASE,
)
_INTERNAL = re.compile(
    r"^internal\b|\binternal\s+(engineering|engineer|audit|auditor|ai|ops|operations|tools|platform|systems|it|hr|"
    r"recruiter|recruiting|transfer|mobility|communications|comms)\b",
    re.IGNORECASE,
)
# an internship that lasts a year is a placement year in UK terms
_YEAR_LONG = re.compile(r"\b(12|13|12\.5|11|10|9)[ -]?months?\b|\byear[- ]long\b")
_APPRENTICE = re.compile(r"\b(apprentice|apprentices|apprenticeship|apprenticeships)\b")

# the recruitment cycle the dashboard and Vitafolio list
CYCLE = (2026, 2027)


def _has(terms, text: str) -> bool:
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) for term in terms)


def classify(title: str):
    """The kind of role the title names; None when it is not a student or graduate role.

    Kinds: internship, placement, insight, graduate and apprenticeship.
    """
    # "post-graduate" names a research or teaching post; joined up it can no longer match "graduate"
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    t = t.replace("post-graduate", "postgraduate").replace("post graduate", "postgraduate")
    if not t:
        return None
    staff = bool(_STAFF.search(t))
    intern = _has(INTERNSHIP, t) and not _INTERNAL.search(t)
    if staff and not intern:
        return None
    if _APPRENTICE.search(t):
        return "apprenticeship"
    if _has(PLACEMENT, t) or (intern and _YEAR_LONG.search(t)):
        return "placement"
    if _has(INSIGHT, t):
        return "insight"
    if _has(GRADUATE, t):
        return "graduate"
    if intern:
        return "internship"
    return None


_RANGE = re.compile(r"\b(20\d\d)\s*[/-]\s*(?:20)?\d\d\b")


def in_cycle(title: str, now=None) -> bool:
    """True when nothing in the title places the role outside the cycle.

    Every year it names must fall within the cycle (a range such as 2027-28 counts by the year it
    starts) and a spring or summer role must not have finished its season.
    """
    now = now or datetime.now(timezone.utc)
    t = (title or "").lower()
    years = [int(y) for y in _RANGE.findall(t)]
    years += [int(y) for y in re.findall(r"\b(20\d\d)\b", _RANGE.sub("", t))]
    if any(y < CYCLE[0] or y > CYCLE[1] for y in years):
        return False
    season = re.search(r"\b(spring|summer)\b", t)
    if years and season:
        ends = datetime(max(years), 6 if season.group(1) == "spring" else 9, 30, 23, 59, tzinfo=timezone.utc)
        if now > ends:
            return False
    return True
