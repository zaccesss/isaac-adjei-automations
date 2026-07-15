"""Tech keywords and the per-category student term lists."""


# I keep the keyword list broad enough to catch hardware, cloud, quant and
# traditional SWE roles because my interests span all of these areas.
TECH_KEYWORDS = [
    "software", "engineer", "developer", "technology", "data", "ai",
    "machine learning", "embedded", "electronic", "hardware", "firmware",
    "fpga", "computer science", "computing", "cyber", "security", "devops",
    "cloud", "backend", "frontend", "fullstack", "full stack", "swe",
    "infrastructure", "networking", "systems", "platform", "reliability",
    "quantitative", "quant", "trading", "research", "analyst",
    # Cloud & infrastructure specific
    "aws", "azure", "gcp", "kubernetes", "k8s", "docker", "terraform",
    "ansible", "serverless", "microservices", "devsecops", "site reliability",
    "solutions architect", "cloud architect", "cloud engineer",
    # Additional tech roles
    "product", "robotics", "automation", "test", "qa", "quality assurance",
    "compiler", "operating system", "kernel", "low latency", "hft",
    "signal processing", "rf", "photonics", "asic", "vlsi", "soc",
]


# ─── PER-CATEGORY STUDENT TERM SETS ────────────────────────────────────────
# I split student terms by category so the scraper can identify the correct
# application type for each role rather than lumping everything into one bag.

INTERNSHIP_TERMS = [
    "intern", "internship", "co-op", "coop", "student researcher",
    "undergraduate researcher", "research intern", "off-cycle intern",
    "summer 2026", "summer intern", "2026 intern", "technology intern",
    "software intern", "engineering intern", "data intern", "ai intern",
    "tech intern",
]

PLACEMENT_TERMS = [
    "placement", "year in industry", "industrial placement",
    "sandwich year", "12 month placement", "12-month placement",
    "year-long placement", "year long placement", "12 months placement",
    "placement year", "industrial year", "work placement",
]

SPRING_WEEK_TERMS = [
    "spring week", "spring insight", "insight week", "insight programme",
    "spring programme", "discovery programme", "explore programme",
    "spring intern", "first year", "penultimate", "women in tech",
    "diversity programme", "access programme",
]

GRADUATE_TERMS = [
    "graduate scheme", "graduate programme", "grad scheme",
    "new grad", "entry level", "early careers",
    "early talent", "technology graduate", "software graduate",
    "engineering graduate", "apprenticeship",
]

EVENT_TERMS = [
    "hackathon", "coding challenge", "coding competition",
    "open day", "careers fair", "workshop", "conference",
    "networking", "virtual event", "online event",
]

# Combined flat list for quick is_student_role checks
STUDENT_TERMS = (
    INTERNSHIP_TERMS + PLACEMENT_TERMS + SPRING_WEEK_TERMS + GRADUATE_TERMS
)
