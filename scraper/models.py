"""The Job shape that flows into the database layer."""
from dataclasses import asdict, dataclass


@dataclass
class Job:
    """One scraped role as insert_job consumes it.

    The sources still build plain dicts today; this dataclass types that contract in
    one place (and backs the tests) so a field cannot drift silently. description
    feeds the AI enrichment only and is never stored.
    """

    company: str
    role: str
    type: str = "Internship"
    url: str = ""
    location: str = ""
    deadline: "str | None" = None
    opening_date: "str | None" = None
    last_year_opening: "str | None" = None
    housing_location: "str | None" = None
    salary_range: str = ""
    work_mode: str = ""
    source: str = ""
    sponsors_visa: "bool | str | None" = None
    category: "str | None" = None
    cv_required: "str | None" = None
    cover_letter_required: "bool | str | None" = None
    written_answers: "str | None" = None
    notes: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
