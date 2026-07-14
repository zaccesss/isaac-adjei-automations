"""Optional AI field extraction: Groq then Gemini then OpenRouter then GitHub Models."""

import os
import re
import time
import json
import requests
from .filters import detect_category

# ─── AI FIELD EXTRACTION (Groq -> Gemini -> OpenRouter, optional) ────────────
# When a new role carries a description, I ask an LLM to pick the correct category tab and extract
# the fields the ATS did not provide (salary, work mode, deadline, visa sponsorship, cover letter).
# It only ever fills genuinely empty scraper-owned fields, keeps the company-based FAANG+/Quant
# categories from the regex, never overrides an ATS value and never touches user-owned columns. Groq
# is tried first, then Gemini, then OpenRouter, so a rate limit or outage on one still leaves a
# working fallback. The whole step is skipped when none of the three keys is set.

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
GH_MODELS_TOKEN = os.environ.get("GH_MODELS_TOKEN", "").strip()
AI_BUDGET = int(os.environ.get("SCRAPER_AI_BUDGET", "150"))
_ai_calls = 0

# The exact category tabs the dashboard groups by - the model must pick one of these or null.
AI_CATEGORIES = {
    "AI and Machine Learning", "Cyber Security", "Data Science", "DevOps and Infrastructure",
    "Embedded", "FAANG+", "Hardware", "IT", "Quant Developer", "Software Engineering",
    "Startups", "Tech Consulting",
}
_AI_WORK_MODES = {
    "remote": "Remote", "hybrid": "Hybrid", "on-site": "On-site",
    "on site": "On-site", "onsite": "On-site", "in-office": "On-site", "in office": "On-site",
}
_AI_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AI_NULLISH = {"", "null", "none", "n/a", "na", "not specified", "unspecified", "not stated"}


def _ai_label(v):
    """Coerce a model value to the 'Yes'/'No'/'Optional' labels the app stores, or None."""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("yes", "true", "required"):
            return "Yes"
        if s in ("no", "false", "not required"):
            return "No"
        if s == "optional":
            return "Optional"
    return None


def _validate_ai(data: dict) -> dict:
    """Validate and coerce raw model output into clean, scraper-owned values."""
    out = {}
    if not isinstance(data, dict):
        return out
    cat = data.get("category")
    if isinstance(cat, str) and cat.strip() in AI_CATEGORIES:
        out["category"] = cat.strip()
    if isinstance(data.get("sponsors_visa"), bool):
        out["sponsors_visa"] = data["sponsors_visa"]
    sal = data.get("salary")
    if isinstance(sal, str) and sal.strip().lower() not in _AI_NULLISH:
        out["salary_range"] = sal.strip()[:120]
    wm = data.get("work_mode")
    if isinstance(wm, str) and wm.strip().lower() in _AI_WORK_MODES:
        out["work_mode"] = _AI_WORK_MODES[wm.strip().lower()]
    dl = data.get("deadline")
    if isinstance(dl, str) and _AI_DATE_RE.match(dl.strip()):
        out["deadline"] = dl.strip()
    cl = _ai_label(data.get("cover_letter_required"))
    if cl is not None:
        out["cover_letter_required"] = cl
    return out


def _build_ai_prompt(snippet: str, title: str, company: str) -> str:
    return (
        "From the job advert below, extract these facts and reply with a JSON object using exactly "
        "these keys. Use null whenever the advert does not state a value - never guess.\n"
        '{"category": one of ["AI and Machine Learning","Cyber Security","Data Science",'
        '"DevOps and Infrastructure","Embedded","FAANG+","Hardware","IT","Quant Developer",'
        '"Software Engineering","Startups","Tech Consulting"], '
        '"sponsors_visa": true|false|null, "salary": string|null, '
        '"work_mode": "Remote"|"Hybrid"|"On-site"|null, "deadline": "YYYY-MM-DD"|null, '
        '"cover_letter_required": true|false|null}\n'
        "category is the single best-fit tab: Embedded for firmware/FPGA/RTOS/robotics, Hardware for "
        "circuit/electronics/chip design, Quant Developer for trading or quant roles, FAANG+ only "
        "for Google/Meta/Amazon/Apple/Microsoft/Netflix/OpenAI/Anthropic/DeepMind. sponsors_visa is "
        "true only if it explicitly offers visa sponsorship, false only if it explicitly rules it "
        "out. salary is the stated pay verbatim. deadline is the closing date.\n\n"
        f"ROLE: {title}\nCOMPANY: {company}\n\nADVERT:\n{snippet}"
    )


def _call_groq(prompt: str):
    if not GROQ_API_KEY:
        return None
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You extract structured facts from job adverts and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 220,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_gemini(prompt: str):
    if not GOOGLE_AI_API_KEY:
        return None
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        # The key travels in a header so an exception's URL text can never carry it.
        headers={"x-goog-api-key": GOOGLE_AI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openrouter(prompt: str):
    if not OPENROUTER_API_KEY:
        return None
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [
                {"role": "system", "content": "You extract structured facts from job adverts and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 220,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_github(prompt: str):
    if not GH_MODELS_TOKEN:
        return None
    resp = requests.post(
        "https://models.github.ai/inference/chat/completions",
        headers={"Authorization": f"Bearer {GH_MODELS_TOKEN}", "Content-Type": "application/json"},
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You extract structured facts from job adverts and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 220,
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


_AI_PROVIDERS = (("Groq", _call_groq), ("Gemini", _call_gemini), ("OpenRouter", _call_openrouter), ("GitHub", _call_github))


def ai_extract(text: str, title: str = "", company: str = "") -> dict:
    """Extract scraper-owned fields from a description, trying Groq -> Gemini -> OpenRouter in turn.
    Returns {} on exhausted budget, no key or total failure, so the scraper degrades gracefully."""
    global _ai_calls
    if _ai_calls >= AI_BUDGET:
        return {}
    snippet = (text or "").strip()[:6000]
    if len(snippet) < 80:
        return {}
    if not (GROQ_API_KEY or GOOGLE_AI_API_KEY or OPENROUTER_API_KEY or GH_MODELS_TOKEN):
        return {}
    _ai_calls += 1
    prompt = _build_ai_prompt(snippet, title, company)
    for name, fn in _AI_PROVIDERS:
        try:
            content = fn(prompt)
        except Exception as e:
            print(f"  ~ AI provider {name} failed: {e}")
            continue
        if not content:
            continue
        try:
            result = _validate_ai(json.loads(content))
        except Exception:
            continue
        time.sleep(1.5)
        return result
    time.sleep(1.5)
    return {}


def _ai_fill(job: dict) -> None:
    """Categorise a new job and fill its empty scraper-owned fields from the description, in place.
    The reliable company-based FAANG+/Quant categories from the regex are kept; the model sets the
    rest of the tabs and never overrides a value the ATS already provided."""
    regex_cat = detect_category(job["company"], job["role"])
    fields_complete = (
        job.get("sponsors_visa") is not None
        and job.get("salary_range")
        and job.get("work_mode")
        and job.get("deadline")
        and job.get("cover_letter_required") is not None
    )
    # Skip the call only when the company-based category is high-confidence and nothing is missing.
    if regex_cat in ("FAANG+", "Quant Developer") and fields_complete:
        job["category"] = regex_cat
        return
    ai = ai_extract(job.get("description", ""), job.get("role", ""), job.get("company", ""))
    # Keep the reliable company-based regex categories, otherwise take the model's tab.
    if regex_cat in ("FAANG+", "Quant Developer"):
        job["category"] = regex_cat
    elif ai.get("category"):
        job["category"] = ai["category"]
    if not ai:
        return
    if ai.get("sponsors_visa") is not None and job.get("sponsors_visa") is None:
        job["sponsors_visa"] = ai["sponsors_visa"]
    if ai.get("salary_range") and not job.get("salary_range"):
        job["salary_range"] = ai["salary_range"]
    if ai.get("work_mode") and not job.get("work_mode"):
        job["work_mode"] = ai["work_mode"]
    if ai.get("deadline") and not job.get("deadline"):
        job["deadline"] = ai["deadline"]
    if ai.get("cover_letter_required") is not None and job.get("cover_letter_required") is None:
        job["cover_letter_required"] = ai["cover_letter_required"]
    print(f"  * AI enriched {job.get('company')} | {job.get('role')} -> {job.get('category')} | {ai}")
