# Cases derived from the inline comments in scraper/ai.py: _validate_ai only ever
# emits clean scraper-owned values and _ai_label coerces to the exact text labels the
# app stores.
from scraper.ai import _ai_label, _validate_ai


def test_non_dict_input_yields_nothing():
    assert _validate_ai(None) == {}
    assert _validate_ai("category: Embedded") == {}


def test_category_must_be_on_the_whitelist():
    assert _validate_ai({"category": "Embedded"})["category"] == "Embedded"
    assert "category" not in _validate_ai({"category": "Basket Weaving"})


def test_sponsors_visa_must_be_a_real_boolean():
    assert _validate_ai({"sponsors_visa": True})["sponsors_visa"] is True
    assert "sponsors_visa" not in _validate_ai({"sponsors_visa": "yes"})


def test_nullish_salaries_are_dropped_and_long_ones_truncated():
    assert "salary_range" not in _validate_ai({"salary": "n/a"})
    assert _validate_ai({"salary": "GBP 45,000"})["salary_range"] == "GBP 45,000"
    assert len(_validate_ai({"salary": "x" * 500})["salary_range"]) == 120


def test_work_modes_coerce_to_the_app_labels():
    assert _validate_ai({"work_mode": "hybrid"})["work_mode"] == "Hybrid"
    assert _validate_ai({"work_mode": "in office"})["work_mode"] == "On-site"
    assert "work_mode" not in _validate_ai({"work_mode": "sometimes"})


def test_dates_must_be_iso_shaped():
    assert _validate_ai({"deadline": "2026-09-30"})["deadline"] == "2026-09-30"
    assert "deadline" not in _validate_ai({"deadline": "next Tuesday"})
    assert _validate_ai({"opening_date": "2026-08-01"})["opening_date"] == "2026-08-01"
    assert "opening_date" not in _validate_ai({"opening_date": "August"})


def test_requirement_labels_cover_cv_and_cover_letter():
    assert _validate_ai({"cover_letter_required": True})["cover_letter_required"] == "Yes"
    assert _validate_ai({"cover_letter_required": "optional"})["cover_letter_required"] == "Optional"
    assert _validate_ai({"cv_required": False})["cv_required"] == "No"
    assert "cv_required" not in _validate_ai({"cv_required": "maybe"})


def test_ai_label_coercions():
    assert _ai_label(True) == "Yes"
    assert _ai_label(False) == "No"
    assert _ai_label("required") == "Yes"
    assert _ai_label("not required") == "No"
    assert _ai_label("Optional") == "Optional"
    assert _ai_label("dunno") is None
    assert _ai_label(None) is None


def test_a_rate_limited_provider_is_benched_for_the_run(monkeypatch):
    import scraper.ai as ai_mod
    from scraper.context import RunContext

    calls = {"limited": 0, "healthy": 0}

    class _FakeLimited(Exception):
        class response:  # mimics requests.HTTPError.response
            status_code = 429

    def limited(prompt):
        calls["limited"] += 1
        raise _FakeLimited()

    def healthy(prompt):
        calls["healthy"] += 1
        return '{"category": "Embedded"}'

    monkeypatch.setattr(ai_mod, "_AI_PROVIDERS", (("Limited", limited), ("Healthy", healthy)))
    monkeypatch.setattr(ai_mod.config, "GROQ_API_KEY", "x")
    monkeypatch.setattr(ai_mod.time, "sleep", lambda s: None)

    ctx = RunContext.bare()
    desc = "An embedded firmware role working on FPGA and RTOS systems in C and C++." * 3
    first = ai_mod.ai_extract(ctx, desc)
    second = ai_mod.ai_extract(ctx, desc)

    assert first == {"category": "Embedded"} and second == {"category": "Embedded"}
    # The 429 benched the limited provider immediately: it is never tried again.
    assert calls["limited"] == 1
    assert calls["healthy"] == 2
    assert ctx.ai_provider_failures["Limited"] >= 3
