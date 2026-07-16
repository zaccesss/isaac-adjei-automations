# The existing-row pre-load must page past PostgREST's 1000-row cap: a bare select
# stops at 1000 and every older row then looks brand new on every run.
from scraper.context import RunContext
from scraper.db import dedupe_key, load_existing_keys


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._window = (0, len(rows) - 1)

    def select(self, *_args):
        return self

    def range(self, start, end):
        self._window = (start, end)
        return self

    def execute(self):
        class _Res:
            pass

        res = _Res()
        start, end = self._window
        # PostgREST returns at most 1000 rows per response whatever the range asks.
        res.data = self._rows[start : min(end + 1, start + 1000)]
        return res


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeQuery(self._rows)


def _rows(n):
    return [
        {"company": f"Company {i}", "role": f"Role {i}", "url": f"https://a.example/jobs/{i}"}
        for i in range(n)
    ]


def test_preload_pages_past_the_1000_row_cap():
    ctx = RunContext.bare()
    ctx.supabase = _FakeClient(_rows(2437))
    load_existing_keys(ctx)
    assert len(ctx.existing_keys) == 2437
    assert len(ctx.existing_urls) == 2437
    assert dedupe_key("Company 2000", "Role 2000", "https://a.example/jobs/2000") in ctx.existing_keys


def test_preload_handles_a_small_table_in_one_page():
    ctx = RunContext.bare()
    ctx.supabase = _FakeClient(_rows(37))
    load_existing_keys(ctx)
    assert len(ctx.existing_keys) == 37
