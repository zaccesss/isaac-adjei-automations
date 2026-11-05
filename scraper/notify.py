"""The end-of-run Discord alert for newly found student roles."""

import requests
from . import config
from .locations import priority_rank

# a text label as well as the order, so the priority never rests on colour alone.
PRIORITY_LABELS = {0: "Top priority: ", 1: "Priority location: ", 2: "Priority location: "}


def order_for_alert(new_jobs: list[dict]) -> list[dict]:
    """The new jobs with the priority places first; the run's own order is kept within a rank."""
    return sorted(new_jobs, key=lambda j: priority_rank(j.get("location", ""), j.get("company", ""), j.get("role", "")))


def alert_line(job: dict) -> str:
    """One alert line: the priority label (if any), the type in bold and the linked role."""
    company = job.get("company", "")
    role = job.get("role", "")
    url = job.get("url", "")
    jtype = job.get("type", "")
    label = f"[{company} - {role}]({url})" if url else f"{company} - {role}"
    prefix = PRIORITY_LABELS.get(priority_rank(job.get("location", ""), company, role), "")
    return f"- {prefix}**{jtype}** {label}"

# ─── DISCORD ALERT ──────────────────────────────────────────────────────────

def send_discord_note(text: str) -> None:
    """Post one plain line to the Discord webhook for a run that skipped a source."""
    if config.DRY_RUN:
        print(f"[dry run] would post a Discord note: {text}")
        return
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url:
        return
    try:
        requests.post(
            webhook_url,
            json={"content": text[:1900]},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as e:
        print(f"Discord note failed: {e}")


def send_discord_alert(new_jobs: list[dict]) -> None:
    if config.DRY_RUN:
        print(f"[dry run] would post a Discord alert for {len(new_jobs)} new student roles.")
        return
    # post new job findings to Discord so alerts appear on phone immediately
    # after the daily scraper run rather than waiting for the Sunday digest.
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url or not new_jobs:
        return

    # batch into chunks of 20 to stay under Discord's embed field limit.
    CHUNK = 20
    ordered = order_for_alert(new_jobs)
    for i in range(0, len(ordered), CHUNK):
        chunk = ordered[i:i + CHUNK]
        lines = [alert_line(j) for j in chunk]

        payload = {
            "embeds": [{
                "title": f"New jobs found ({len(new_jobs)} total)",
                "description": "\n".join(lines),
                "color": 0x5865F2,
            }]
        }
        try:
            requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
        except Exception as e:
            # the exception text can echo the webhook URL, which is itself the credential.
            print(f"  Discord alert failed: {type(e).__name__}")
