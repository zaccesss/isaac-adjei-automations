"""The end-of-run Discord alert for newly found student roles."""

import os
import requests

# ─── DISCORD ALERT ──────────────────────────────────────────────────────────

def send_discord_alert(new_jobs: list[dict]) -> None:
    # I post new job findings to Discord so alerts appear on phone immediately
    # after the daily scraper run rather than waiting for the Sunday digest.
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url or not new_jobs:
        return

    # I batch into chunks of 20 to stay under Discord's embed field limit.
    CHUNK = 20
    for i in range(0, len(new_jobs), CHUNK):
        chunk = new_jobs[i:i + CHUNK]
        lines = []
        for j in chunk:
            company = j.get("company", "")
            role = j.get("role", "")
            url = j.get("url", "")
            jtype = j.get("type", "")
            label = f"[{company} - {role}]({url})" if url else f"{company} - {role}"
            lines.append(f"- **{jtype}** {label}")

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
            # The exception text can echo the webhook URL, which is itself the credential.
            print(f"  Discord alert failed: {type(e).__name__}")
