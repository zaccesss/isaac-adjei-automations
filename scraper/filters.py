"""Relevance: student-role detection, tech keywords, type inference and category detection."""

import re
from .data.companies import PRIORITY_COMPANIES, STUDENT_DEPTS
from .data.keywords import EVENT_TERMS, TECH_KEYWORDS
from .locations import is_location_ok
from .roles import classify

# use whole-word matching for "intern" so words like "internal" and
# "international" do not trigger a false positive intern classification.
_INTERN_WHOLE_WORD_RE = re.compile(
    r'\b(intern|internship|internships|interns)\b', re.IGNORECASE
)
_EXCLUDE_INTERN_RE = re.compile(
    r'\b(internal|international|internally)\b', re.IGNORECASE
)

# catch "Internal <function>" patterns that appear mid-title (not just at the start).
# e.g. "Lead Engineer, Internal Engineering" or "Staff PM - Internal AI".
_INTERNAL_FUNCTION_RE = re.compile(
    r'\binternal\s+(engineering|engineer|audit|auditor|ai|ops|operations|'
    r'tools|platform|systems|it\b|hr\b|recruiter|recruiting|transfer|mobility)',
    re.IGNORECASE
)

# skip the department-name fallback for clearly senior or non-student titles
# so MongoDB / Adyen roles tagged under a university dept do not slip through.
_SENIOR_ROLE_RE = re.compile(
    r'\b(staff|senior|sr\.?|lead|principal|architect|director|vp\b|'
    r'vice president|head of|manager|recruiter|auditor|contractor|'
    r'contract\b|associate recruiter|ii|iii|iv)\b',
    re.IGNORECASE
)


# ─── RELEVANCE ──────────────────────────────────────────────────────────────


# term matching is whole-word from July 2026: plain substring checks let
# "replacement" and "outplacement" count as placement roles, "Repair Technician"
# pass the tech check through the bare letters "ai" and "Workshop Engineer" look
# like a careers event. Multi-word terms keep their internal spaces; every term
# is boundary-anchored.

def _any_word(terms, text: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


# short tech keywords that are common letter runs inside ordinary words get
# whole-word treatment; the longer keywords stay as substrings so "cybersecurity"
# still matches "cyber" and "fullstack" still matches "full stack" variants.
_WHOLE_WORD_TECH = {"ai", "rf", "qa", "swe", "hft", "asic", "vlsi", "soc", "fpga", "test", "quant"}


def _has_tech_keyword(title_lower: str) -> bool:
    for k in TECH_KEYWORDS:
        if k in _WHOLE_WORD_TECH:
            if re.search(rf"\b{re.escape(k)}\b", title_lower):
                return True
        elif k in title_lower:
            return True
    return False


# titles that are commercial, people or back-office roles are never tracked,
# whatever else the title contains - this kills the sales and recruiting noise
# that priority companies otherwise wash in through the looser location filter.
_NON_TECH_ROLE_RE = re.compile(
    r"\b(sales|account (executive|manager)|business development|recruiter|"
    r"recruiting|talent acquisition|marketing|paralegal|legal counsel|"
    r"accountant|payroll|procurement|customer success|copywriter|"
    r"community manager|hr\b|people operations|office manager)\b",
    re.IGNORECASE,
)


def is_student_role(
    title: str, dept_names: list[str] | None = None
) -> bool:
    """Return True if this role is student/intern/placement facing.

    The title is read by the shared rules in roles.py, the same ones Vitafolio uses: whole words
    only, staff and senior titles left out and apprenticeships kept off the dashboard. Careers events
    still count through the event terms.
    """
    kind = classify(title)
    if kind == "apprenticeship" or _INTERNAL_FUNCTION_RE.search(title or ""):
        return False
    if kind is not None:
        return True
    if not _SENIOR_ROLE_RE.search(title or "") and _any_word(EVENT_TERMS, (title or "").lower()):
        return True

    # fall back to department names as a secondary signal for companies that
    # route all graduate roles through a dedicated department without labelling
    # each title individually (e.g. Bloomberg "University Recruiting" dept).
    # skip this fallback for clearly senior or non-student titles so that
    # priority companies like MongoDB with a university dept do not accidentally
    # pull Staff / Lead / Recruiter / Auditor roles into the student pipeline.
    if dept_names and not _SENIOR_ROLE_RE.search(title):
        d = " ".join(dept_names).lower()
        if any(term in d for term in STUDENT_DEPTS):
            return True
    return False


def is_relevant_job(
    title: str,
    company: str = "",
    location: str = "",
) -> bool:
    """True if this is a full-time tech role for the Jobs tab.

    Jobs use the same UK/Europe location filter as internships - no point
    showing a San Francisco full-time role to someone based in the UK.
    """
    if is_student_role(title, None):
        return False
    if not _has_tech_keyword(title.lower()):
        return False
    if _NON_TECH_ROLE_RE.search(title):
        return False
    is_priority = any(p in company.lower() for p in PRIORITY_COMPANIES)
    return is_location_ok(location, is_priority)


def is_relevant(
    title: str,
    company: str,
    location: str = "",
    dept_names: list[str] | None = None,
) -> bool:
    """True if this internship/placement/graduate role should be saved.

    Requires student term + tech keyword + UK/Europe location. The location
    check accepts any UK city, Remote/Hybrid and major European tech hubs.
    For priority companies an empty or unknown location is also accepted
    because they often have UK offices not labelled in every posting.
    """
    if not is_student_role(title, dept_names):
        return False
    if not _has_tech_keyword(title.lower()):
        return False
    if _NON_TECH_ROLE_RE.search(title):
        return False
    is_priority = any(p in company.lower() for p in PRIORITY_COMPANIES)
    return is_location_ok(location, is_priority)


# the dashboard's type names for the shared kinds of role
_TYPE_FOR_KIND = {
    "internship": "Internship",
    "placement": "Industrial Placement",
    "insight": "Spring Week",
    "graduate": "Graduate",
}


def infer_type(title: str, default: str = "Internship") -> str:
    """Determine the application type from the role title using the shared rules in roles.py.

    A careers event keeps the Event type, a senior or signal-free title falls back as before.
    """
    kind = classify(title)
    if kind in _TYPE_FOR_KIND:
        return _TYPE_FOR_KIND[kind]
    t = (title or "").lower()
    if _SENIOR_ROLE_RE.search(title or "") and not _INTERN_WHOLE_WORD_RE.search(t):
        return "Full-time Job"
    if _any_word(EVENT_TERMS, t):
        return "Event"
    if kind == "apprenticeship" or _SENIOR_ROLE_RE.search(title or ""):
        return "Full-time Job"
    return default

def resolve_type(title: str, fallback: str = "Internship") -> str:
    """infer_type with an honest default for signal-free titles.

    A title with no student signal at all is a full-time job whatever tab it
    used to sit in - "Networking Architect" carries nothing student-facing, so
    it must never keep an Internship or Event label. Student-facing titles
    whose specific type cannot be read fall back to the caller's default.
    """
    if not is_student_role(title, None):
        return infer_type(title, default="Full-time Job")
    return infer_type(title, default=fallback)



_FAANG = {"google", "meta", "amazon", "apple", "microsoft", "netflix", "deepmind", "openai", "anthropic"}
_QUANT_COMPANIES = {"citadel", "optiver", "jane street", "imc", "jump", "two sigma", "susquehanna", "hudson river", "de shaw", "akuna", "virtu", "sig ", "drw", "flow traders"}
_AI_RE = re.compile(r'\bai\b')

def detect_category(company: str, role: str) -> str:
    c = company.lower()
    r = role.lower()
    if any(f in c for f in _FAANG):
        return "FAANG+"
    if any(q in c for q in _QUANT_COMPANIES) or any(t in r for t in ("quant", "trading", "algorithmic", "derivatives", "fixed income")):
        return "Quant Developer"
    if (_AI_RE.search(r) or any(t in r for t in ("machine learning", "artificial intelligence", "deep learning", "llm", "generative ai", "nlp", "computer vision", "neural network"))):
        return "AI and Machine Learning"
    if any(t in r for t in ("data science", "data scientist", "data analyst", "data engineer", "analytics engineer", "business intelligence", "bi analyst")):
        return "Data Science"
    if any(t in r for t in ("embedded", "firmware", "fpga", "vhdl", "rtos", "bare metal", "hardware engineer", "electronics engineer", "circuit", "microcontroller", "iot engineer")):
        return "Embedded"
    if any(t in r for t in ("devops", "devsecops", "cloud engineer", "cloud developer", "site reliability", "sre", "platform engineer", "infrastructure engineer", "kubernetes", "terraform", "aws engineer", "azure engineer", "gcp ")):
        return "DevOps and Infrastructure"
    if any(t in r for t in ("security", "cyber", "penetration", "pen test", "soc analyst", "information security", "appsec", "threat")):
        return "Cyber Security"
    if any(t in r for t in ("consult", "advisory", "business analyst", "management information")):
        return "Tech Consulting"
    if any(t in r for t in ("it support", "service desk", "it technician", "helpdesk", "1st line", "2nd line")):
        return "IT"
    return "Software Engineering"
