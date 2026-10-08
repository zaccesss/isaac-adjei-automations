"""Relevance: student-role detection, tech keywords, type inference and category detection."""

import re
from .data.companies import PRIORITY_COMPANIES, STUDENT_DEPTS
from .data.keywords import EVENT_TERMS
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


# the roles this tracker follows: computing, electronics, data and quant work plus the wider
# engineering disciplines (mechanical, civil, aerospace, energy). Every term is a whole word, so
# "ai" never matches inside "maintain" and "it" never inside "with". Broad words that also name
# non-technical work ("analyst", "product", "research") are deliberately left out.
_TECH_OR_ENGINEERING_RE = re.compile(
    r"\b(software|developers?|development engineer|programmer|programming|coding|engineer|engineers|"
    r"engineering|data|machine learning|ai|ml|artificial intelligence|deep learning|computer vision|"
    r"nlp|llm|cyber|cybersecurity|security engineer|cloud|devops|devsecops|sre|site reliability|"
    r"hardware|electronic|electronics|electrical|embedded|firmware|fpga|asic|vlsi|rf|semiconductor|"
    r"silicon|chip|pcb|photonics|robotics|mechatronics|quant|quants|quantitative|algorithmic|trading|"
    r"trader|technology|technologies|tech|it|computing|computer|computational|digital|systems|"
    r"network|networks|infrastructure|platform|web|mobile|ios|android|qa|test|testing|automation|"
    r"analytics|scientist|physics|mathematics|maths|statistics|mechanical|civil|structural|"
    r"aerospace|aeronautical|avionics|manufacturing|process|chemical|nuclear|energy|materials|"
    r"automotive|power|telecoms?|telecommunications|wireless|signal processing|space|satellite|"
    r"defence|design engineer|cad|simulation|modelling|operational technology|ot|backend|back-end|frontend|"
    r"front-end|full stack|full-stack|fullstack|soc|verification|validation|nand|dram|memory|reliability|"
    r"technical|gpu|cpu|compiler|compilers|kernel|linux|database|databases|sql|python|java|"
    r"research engineer|research scientist|communications engineer|communications engineering|quantum|"
    r"solutions architect|software architect|cloud architect)\b",
    re.IGNORECASE,
)


def _has_tech_keyword(title_lower: str) -> bool:
    """True when the title names computing, electronics, data, quant or engineering work."""
    return bool(_TECH_OR_ENGINEERING_RE.search(title_lower or ""))


# commercial, people and back-office roles are never tracked, whatever else the title says:
# a technology word next to them ("HR Technology Analyst", "Investment Banking, Technology")
# does not make the work technical
_NON_TECH_ROLE_RE = re.compile(
    r"\b(sales|account (executive|manager)|business development|recruiter|recruiting|recruitment|"
    r"talent acquisition|human resources|hr|people operations|marketing|paralegal|legal|lawyer|"
    r"solicitor|accountant|accounting|payroll|procurement|sourcing|supply chain|customer success|"
    r"customer service|copywriter|editorial|editing|journalism|journalist|community manager|"
    r"office manager|compliance|private equity|investment banking|corporate banking|global banking|"
    r"banking analyst|investment analyst|financial analyst|finance analyst|wealth|hospitality|"
    r"food|retail|real estate|events|internal communications|corporate communications|public relations|"
    r"actuarial|insurance analyst|risk analyst|credit analyst|kyc|capital markets|"
    r"(?<!technology )audit(?! technology)|(?<!it )auditor|tax(?! technology))\b",
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
    """True if this is a full-time computing, electronics, data or quant role for the Jobs tab.

    Full-time roles in the wider engineering disciplines are left out so the Jobs tab stays
    focused; student roles in them are kept under Other Engineering.
    """
    if is_student_role(title, None):
        return False
    if not _has_tech_keyword(title.lower()) or detect_category(company, title) == "Other Engineering":
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

    Requires a student term and a tech keyword with no non-tech role word. Where it is decides
    only which tab it lands in, UK or Abroad, so the final gate in insert_job settles location.
    """
    if not is_student_role(title, dept_names):
        return False
    if not _has_tech_keyword(title.lower()):
        return False
    return not _NON_TECH_ROLE_RE.search(title)


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

def _has(pattern: str, text: str) -> bool:
    return bool(re.search(rf"\b(?:{pattern})\b", text))


def detect_category(company: str, role: str) -> str:
    """The dashboard category for a role: the employer first for FAANG+ and the trading firms,
    then the role's own words, most specific first. Whole words only throughout."""
    c = (company or "").lower()
    r = (role or "").lower()
    if any(f in c for f in _FAANG):
        return "FAANG+"
    if any(q in c for q in _QUANT_COMPANIES) or _has(r"quant|quants|quantitative|algorithmic trading|trader|trading|market making|derivatives", r):
        return "Quant Developer"
    if _has(r"ai|ml|machine learning|artificial intelligence|deep learning|llm|generative ai|nlp|computer vision|neural networks?|reinforcement learning", r):
        return "AI and Machine Learning"
    if _has(r"cyber|cybersecurity|security|penetration|pen test|soc analyst|appsec|threat", r):
        return "Cyber Security"
    if _has(r"data science|data scientist|data analyst|data analytics|data engineer|data engineering|analytics engineer|business intelligence|bi analyst|data", r):
        return "Data Science"
    if _has(r"embedded|firmware|fpga|vhdl|verilog|rtos|bare metal|microcontroller|iot", r):
        return "Embedded"
    if _has(r"hardware|electronic|electronics|electrical|rf|asic|vlsi|semiconductor|silicon|chip|pcb|analogue|analog|photonics|power electronics|wireless|telecoms?|signal processing", r):
        return "Hardware"
    if _has(r"devops|devsecops|cloud|site reliability|sre|platform engineer|infrastructure engineer|kubernetes|terraform", r):
        return "DevOps and Infrastructure"
    if _has(r"it support|service desk|it technician|helpdesk|it operations|it intern|it engineer|information technology|it|end user", r):
        return "IT"
    if _has(r"consulting|consultant|advisory|business analyst|technology analyst|change management|management information", r):
        return "Tech Consulting"
    if _has(r"mechanical|civil|structural|structures|bridges?|highways|traffic|rail|railway|tunnelling|geotechnical|drainage|water|wastewater|building services|surveying|aerospace|aeronautical|avionics|manufacturing|process engineer|chemical|nuclear|energy|materials|automotive|mechatronics|robotics|systems engineering|systems engineer|design engineer|production engineer|operations engineer|quality engineer|test engineer|landing gear|propulsion|thermal|fluids|space|satellite", r) and not _has(r"software|developer|programmer", r):
        return "Other Engineering"
    # an engineering title with no computing word is one of the wider disciplines
    if _has(r"engineer|engineers|engineering|aerodynamics|lethality|warheads?|propulsion|fuel systems", r) and not _has(
        r"software|developer|programmer|technology|tech|digital|data|it|cloud|web|computing|computer|systems engineer|devops", r
    ):
        return "Other Engineering"
    return "Software Engineering"
