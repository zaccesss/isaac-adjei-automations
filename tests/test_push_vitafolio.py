# tests/test_push_vitafolio.py
#
# the advert lookup only trusts Greenhouse, Lever and Ashby's own hosts, matched exactly.

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("push", Path(__file__).parent.parent / "scripts" / "push-vitafolio-jobs.py")
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)


def test_real_job_hosts_are_recognised():
    assert push.board_of("https://boards.greenhouse.io/acme/jobs/123") == ("greenhouse", "acme", "123")
    assert push.board_of("https://job-boards.greenhouse.io/acme/jobs/123") == ("greenhouse", "acme", "123")
    assert push.board_of("https://jobs.lever.co/acme/abc-123") == ("lever", "acme", "abc-123")
    assert push.board_of("https://jobs.ashbyhq.com/acme/xyz") == ("ashby", "acme", "xyz")


def test_look_alike_hosts_are_not_trusted():
    assert push.board_of("https://evilgreenhouse.io/acme/jobs/123") is None
    assert push.board_of("https://greenhouse.io.evil.com/acme/jobs/123") is None
    assert push.board_of("https://jobs.lever.co.evil.com/acme/abc") is None
