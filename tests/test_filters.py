# Cases derived from the inline comments in scraper/filters.py: the whole-word intern
# match, the Internal exclusions, the senior-title guard on the department fallback and
# the per-category ordering of infer_type.
from scraper.filters import detect_category, infer_type, is_relevant, is_student_role


def test_internal_titles_are_rejected():
    assert not is_student_role("Internal Engineering Lead", None)
    assert not is_student_role("Lead Engineer, Internal Engineering", None)
    assert not is_student_role("Staff PM - Internal AI", None)


def test_international_never_counts_as_intern():
    assert not is_student_role("International Business Manager", None)
    # Even alongside a real intern word, the exclusion wins for safety.
    assert not is_student_role("International Sales Intern", None)


def test_whole_word_intern_matches():
    assert is_student_role("Software Intern", None)
    assert is_student_role("Internship 2026 - Data", None)
    assert not is_student_role("Internally Facing Tools Engineer", None)


def test_placement_and_event_terms_match():
    assert is_student_role("Software Engineer Year in Industry", None)
    assert is_student_role("Engineering Careers Fair", None)


def test_senior_titles_skip_the_department_fallback():
    assert not is_student_role("Staff Engineer", ["University Recruiting"])
    assert not is_student_role("Associate Recruiter", ["Early Talent"])
    assert is_student_role("Software Engineer", ["University Recruiting"])


def test_infer_type_prefers_the_specific_terms():
    assert infer_type("Software Industrial Placement Intern") == "Industrial Placement"
    assert infer_type("Technology Spring Week") == "Spring Week"
    assert infer_type("Technology Graduate Scheme") == "Graduate"
    assert infer_type("Engineering Open Day") == "Event"
    assert infer_type("Data Intern") == "Internship"
    assert infer_type("Senior Software Engineer") == "Full-time Job"
    assert infer_type("Software Role") == "Internship"  # the default


def test_is_relevant_requires_student_tech_and_location():
    assert is_relevant("Software Intern", "Acme", "London")
    assert not is_relevant("Marketing Intern", "Acme", "London")
    assert not is_relevant("Software Intern", "Acme", "New York")


def test_detect_category_company_first_then_title():
    assert detect_category("Google", "Marketing Intern") == "FAANG+"
    assert detect_category("Optiver", "Software Intern") == "Quant Developer"
    assert detect_category("Acme", "Machine Learning Intern") == "AI and Machine Learning"
    assert detect_category("Acme", "Firmware Engineer Intern") == "Embedded"
    assert detect_category("Acme", "Software Intern") == "Software Engineering"
