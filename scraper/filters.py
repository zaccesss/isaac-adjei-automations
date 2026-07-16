"""Relevance: student-role detection, tech keywords, type inference and category detection."""

import re
from .data.companies import PRIORITY_COMPANIES, STUDENT_DEPTS
from .data.keywords import EVENT_TERMS, GRADUATE_TERMS, PLACEMENT_TERMS, SPRING_WEEK_TERMS, TECH_KEYWORDS
from .locations import is_location_ok

# I use whole-word matching for "intern" so words like "internal" and
# "international" do not trigger a false positive intern classification.
_INTERN_WHOLE_WORD_RE = re.compile(
    r'\b(intern|internship|internships|interns)\b', re.IGNORECASE
)
_EXCLUDE_INTERN_RE = re.compile(
    r'\b(internal|international|internally)\b', re.IGNORECASE
)

# I catch "Internal <function>" patterns that appear mid-title (not just at the start).
# e.g. "Lead Engineer, Internal Engineering" or "Staff PM - Internal AI".
_INTERNAL_FUNCTION_RE = re.compile(
    r'\binternal\s+(engineering|engineer|audit|auditor|ai|ops|operations|'
    r'tools|platform|systems|it\b|hr\b|recruiter|recruiting|transfer|mobility)',
    re.IGNORECASE
)

# I skip the department-name fallback for clearly senior or non-student titles
# so MongoDB / Adyen roles tagged under a university dept do not slip through.
_SENIOR_ROLE_RE = re.compile(
    r'\b(staff|senior|sr\.?|lead|principal|architect|director|vp\b|'
    r'vice president|head of|manager|recruiter|auditor|contractor|'
    r'contract\b|associate recruiter|ii|iii|iv)\b',
    re.IGNORECASE
)


# ─── RELEVANCE ──────────────────────────────────────────────────────────────


# Term matching is whole-word from July 2026: plain substring checks let
# "replacement" and "outplacement" count as placement roles, "Repair Technician"
# pass the tech check through the bare letters "ai" and "Workshop Engineer" look
# like a careers event. Multi-word terms keep their internal spaces; every term
# is boundary-anchored.

def _any_word(terms, text: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


# Short tech keywords that are common letter runs inside ordinary words get
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


# Titles that are commercial, people or back-office roles are never what I track,
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

    I use whole-word regex for intern-related terms to avoid false positives
    from words like "internal", "international" and "internally". If those
    words appear without a stronger signal (placement, spring week, etc.) the
    role is treated as full-time.
    """
    # I reject titles that begin with "Internal" because those describe
    # internal team-facing roles (e.g. "Internal Engineering"), not student
    # positions. This is separate from the intern-word exclusion below.
    if re.match(r'^internal\b', title.strip(), re.IGNORECASE):
        return False

    # I also reject "Internal <function>" anywhere in the title (e.g. "Lead
    # Engineer, Internal Engineering" or "PM - Internal AI"). These are always
    # full-time internal-team roles regardless of which company posted them.
    if _INTERNAL_FUNCTION_RE.search(title):
        return False

    # I check the title first because it is always present.
    t = title.lower()

    # Non-intern student terms (placement, graduate, spring, event) are safe
    # to match with a simple substring check - none share a root with common
    # English words that would produce false positives.
    NON_INTERN_TERMS = PLACEMENT_TERMS + SPRING_WEEK_TERMS + GRADUATE_TERMS + EVENT_TERMS
    if _any_word(NON_INTERN_TERMS, t):
        return True

    # For intern-family terms I require a whole-word match AND no explicit
    # exclusion word ("internal", "international", "internally").
    has_intern_word = _INTERN_WHOLE_WORD_RE.search(t)
    has_exclude_word = _EXCLUDE_INTERN_RE.search(t)
    if has_intern_word and not has_exclude_word:
        return True

    # I fall back to department names as a secondary signal for companies that
    # route all graduate roles through a dedicated department without labelling
    # each title individually (e.g. Bloomberg "University Recruiting" dept).
    # I skip this fallback for clearly senior or non-student titles so that
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


def infer_type(title: str, default: str = "Internship") -> str:
    """Determine application type from the role title using per-category term sets.

    I check placement and spring week terms first because they are more
    specific than the general 'intern' / 'summer' terms. Graduate schemes
    and events are checked last.
    """
    t = title.lower()
    # A senior title with no intern word is a full-time role whatever else the
    # title mentions - "Senior Engineer, Placement Supervision" is a job, not a
    # placement. Intern-worded senior titles (rare) keep their student typing.
    if _SENIOR_ROLE_RE.search(title) and not _INTERN_WHOLE_WORD_RE.search(t):
        return "Full-time Job"
    # Industrial Placement - 12-month / year in industry
    if _any_word(PLACEMENT_TERMS, t):
        return "Industrial Placement"
    # Spring Week / Insight
    if _any_word(SPRING_WEEK_TERMS, t):
        return "Spring Week"
    # Graduate Scheme
    if _any_word(GRADUATE_TERMS, t):
        return "Graduate"
    # Events
    if _any_word(EVENT_TERMS, t):
        return "Event"
    # General Internship - I use whole-word regex here so "international" and
    # "internationally" do not trigger a false intern classification.
    if _INTERN_WHOLE_WORD_RE.search(t) and not _EXCLUDE_INTERN_RE.search(t):
        return "Internship"
    # I check seniority terms before falling through to the default so that
    # senior roles without any student-term do not get classified as Internship.
    if _SENIOR_ROLE_RE.search(title):
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
