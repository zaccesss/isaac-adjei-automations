"""Shared failure reporter for the Python jobs. When a job raises, I post the full traceback - plus a
link to the exact Actions run - to the #errors channel, then re-raise so the workflow still fails and
the Healthchecks /fail ping fires. Best-effort: a webhook problem never hides the original error, which
always goes to the run log too. Wire it in by wrapping the entrypoint: `with guard("<slug>"): main()`."""

import json
import os
import sys
import traceback
import urllib.request
from contextlib import contextmanager


def _run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""


def post_failure(job: str, exc: BaseException) -> None:
    webhook = os.environ.get("DISCORD_WEBHOOK_ERRORS", "")
    if not webhook:
        return
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if len(tb) > 1500:
        tb = tb[:1500] + "\n... truncated, full trace in the run log"
    url = _run_url()
    parts = [f"\U0001F534 **{job}** failed"]
    if url:
        parts.append(f"↳ {url}")
    parts += ["```", tb, "```"]
    content = "\n".join(parts)
    try:
        req = urllib.request.Request(
            webhook,
            data=json.dumps({"content": content}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)  # noqa: S310  trusted webhook URL from a secret
    except Exception as exc:  # noqa: BLE001  alerting is best-effort, never mask the real error
        print(f"could not post to #errors: {exc}", file=sys.stderr)


@contextmanager
def guard(job: str):
    """Wrap a job's main() so any exception is reported in full to #errors, then re-raised so the
    process still exits non-zero."""
    try:
        yield
    except BaseException as exc:  # noqa: BLE001  report everything, then re-raise
        traceback.print_exc()
        post_failure(job, exc)
        raise
