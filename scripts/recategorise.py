"""
One-off backfill: re-categorise existing scraped applications into the correct dashboard tabs using
the same Groq -> Gemini -> OpenRouter chain the scraper uses. Old rows have no stored description, so
it categorises from title + company only - still far better than the original regex, which dumped 74%
of roles into "Software Engineering" and never produced the Hardware or Startups tabs at all.

It keeps the reliable company-based FAANG+/Quant categories, updates ONLY the category column (never
status, notes, starred, applied_date or any user field), and is safe to re-run. Set
RECATEGORISE_DRY_RUN=1 to preview the changes without writing them.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and at least one of GROQ_API_KEY /
GOOGLE_AI_API_KEY / OPENROUTER_API_KEY.
"""

import os
import sys
import json
import time

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
DRY_RUN = bool(os.environ.get("RECATEGORISE_DRY_RUN", "").strip())
BATCH = 40

CATEGORIES = {
    "AI and Machine Learning", "Cyber Security", "Data Science", "DevOps and Infrastructure",
    "Embedded", "FAANG+", "Hardware", "IT", "Quant Developer", "Software Engineering",
    "Startups", "Tech Consulting",
}
_FAANG = {"google", "meta", "amazon", "apple", "microsoft", "netflix", "deepmind", "openai", "anthropic"}
_QUANT = {
    "citadel", "optiver", "jane street", "imc", "jump", "two sigma", "susquehanna", "hudson river",
    "de shaw", "akuna", "virtu", "drw", "flow traders",
}


def company_category(company: str):
    """The high-confidence company-based tabs, kept exactly as the scraper's regex assigns them."""
    c = (company or "").lower()
    if any(f in c for f in _FAANG):
        return "FAANG+"
    if any(q in c for q in _QUANT):
        return "Quant Developer"
    return None


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_scraped() -> list[dict]:
    """Read every scraped row, paginating past PostgREST's 1000-row cap."""
    rows, offset = [], 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/applications",
            params={
                "select": "id,company,role,category",
                "status": "eq.scraped",
                "order": "id",
                "limit": 1000,
                "offset": offset,
            },
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += 1000


def update_category(row_id, category: str) -> None:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/applications",
        params={"id": f"eq.{row_id}"},
        headers=_headers(),
        json={"category": category},
        timeout=30,
    )
    resp.raise_for_status()


def _call_groq(prompt: str):
    if not GROQ_API_KEY:
        return None
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You categorise job adverts and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 900,
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_gemini(prompt: str):
    if not GOOGLE_AI_API_KEY:
        return None
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        params={"key": GOOGLE_AI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        },
        timeout=45,
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
                {"role": "system", "content": "You categorise job adverts and reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 900,
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


_PROVIDERS = (("Groq", _call_groq), ("Gemini", _call_gemini), ("OpenRouter", _call_openrouter))


def ai_categorise(batch: list[tuple]) -> dict:
    """batch = list of (index, role, company). Returns {index: category} for valid categories only."""
    lines = "\n".join(f"{i}. {role} | {company}" for i, role, company in batch)
    prompt = (
        "Categorise each job below into exactly one of these tabs:\n"
        '["AI and Machine Learning","Cyber Security","Data Science","DevOps and Infrastructure",'
        '"Embedded","FAANG+","Hardware","IT","Quant Developer","Software Engineering","Startups",'
        '"Tech Consulting"]\n'
        "Embedded for firmware/FPGA/RTOS roles, Hardware for circuit/electronics/chip design, Quant "
        "Developer for trading or quant roles, Startups for clearly early-stage startup roles, FAANG+ "
        "only for Google/Meta/Amazon/Apple/Microsoft/Netflix/OpenAI/Anthropic/DeepMind.\n"
        'Reply with JSON {"results": [{"i": <number>, "category": <tab>}, ...]} covering every job.\n\n'
        f"JOBS (number | role | company):\n{lines}"
    )
    for name, fn in _PROVIDERS:
        try:
            content = fn(prompt)
        except Exception as exc:
            print(f"  ~ {name} failed: {exc}")
            continue
        if not content:
            continue
        try:
            data = json.loads(content)
        except Exception:
            continue
        out = {}
        for item in (data.get("results") or []):
            try:
                idx = int(item.get("i"))
            except (TypeError, ValueError):
                continue
            cat = item.get("category")
            if isinstance(cat, str) and cat.strip() in CATEGORIES:
                out[idx] = cat.strip()
        if out:
            return out
    return {}


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    if not (GROQ_API_KEY or GOOGLE_AI_API_KEY or OPENROUTER_API_KEY):
        sys.exit("Set at least one of GROQ_API_KEY / GOOGLE_AI_API_KEY / OPENROUTER_API_KEY.")

    rows = fetch_scraped()
    # Only touch the "Software Engineering" catch-all - rows already sorted into a specific tab are
    # left exactly as they are, so a category that is already correct can never be changed.
    rows = [r for r in rows if (r.get("category") or "") == "Software Engineering"]
    print(f"Loaded {len(rows)} 'Software Engineering' rows to re-categorise. DRY_RUN={DRY_RUN}")

    changed = 0
    pending = []
    # First lock in the reliable company-based categories.
    for r in rows:
        cc = company_category(r.get("company"))
        if cc:
            if r.get("category") != cc:
                if not DRY_RUN:
                    update_category(r["id"], cc)
                changed += 1
                print(f"  {r.get('company')} | {r.get('role')}: {r.get('category')} -> {cc}")
        else:
            pending.append(r)

    # Categorise the rest in batches through the AI.
    for start in range(0, len(pending), BATCH):
        chunk = pending[start:start + BATCH]
        result = ai_categorise([(i, c.get("role", ""), c.get("company", "")) for i, c in enumerate(chunk)])
        for i, c in enumerate(chunk):
            cat = result.get(i)
            if cat and cat != c.get("category"):
                if not DRY_RUN:
                    update_category(c["id"], cat)
                changed += 1
                print(f"  {c.get('company')} | {c.get('role')}: {c.get('category')} -> {cat}")
        print(f"  ...processed {min(start + BATCH, len(pending))}/{len(pending)}")
        time.sleep(5)

    print(f"Done. {changed} categor{'y' if changed == 1 else 'ies'} {'would change' if DRY_RUN else 'changed'}.")


if __name__ == "__main__":
    main()
