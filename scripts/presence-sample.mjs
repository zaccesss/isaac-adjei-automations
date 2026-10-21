// records Discord presence from Lanyard into presence_samples (status and platforms) and
// presence_sessions (games, films and coding, one row per session) every 15 minutes, so the
// dashboard's Presence page can chart what was played, watched and coded over time. Spotify is
// skipped because listening_history already holds every play; custom statuses are skipped too.
// Node only, no deps.

import { guard } from "./lib/report-failure.mjs"

guard("presence-sample")

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const USER_ID = process.env.DISCORD_USER_ID

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!USER_ID) {
  console.log("DISCORD_USER_ID not set - skipping.")
  process.exit(0)
}

// an activity with no start timestamp counts as the same session while it was seen within this window
const SAME_SESSION_MS = 20 * 60 * 1000

const headers = {
  apikey: SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  "Content-Type": "application/json",
}

async function db(path, init = {}) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { ...init, headers: { ...headers, ...(init.headers || {}) } })
  if (!res.ok) throw new Error(`${init.method || "GET"} ${path.split("?")[0]} ${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

async function lanyard() {
  for (let i = 0; i < 3; i++) {
    const res = await fetch(`https://api.lanyard.rest/v1/users/${USER_ID}`)
    if (res.ok) return (await res.json()).data
    if (i < 2) await new Promise((r) => setTimeout(r, 1500 * (i + 1)))
  }
  throw new Error("Lanyard did not answer after 3 tries")
}

async function main() {
  const data = await lanyard()
  const now = new Date()
  const activities = (data.activities || []).filter((a) => a.type !== 4 && !(a.type === 2 && /spotify/i.test(a.name)))

  await db("presence_samples?on_conflict=at", {
    method: "POST",
    headers: { Prefer: "resolution=ignore-duplicates" },
    body: JSON.stringify({
      at: now.toISOString(),
      discord_status: data.discord_status || "offline",
      activity_count: activities.length,
      on_desktop: Boolean(data.active_on_discord_desktop),
      on_mobile: Boolean(data.active_on_discord_mobile),
      on_web: Boolean(data.active_on_discord_web),
    }),
  })

  for (const a of activities) {
    const fields = { details: a.details || null, state: a.state || null, last_seen_at: now.toISOString() }
    if (a.timestamps?.start) {
      const startedAt = new Date(a.timestamps.start).toISOString()
      const found = await db(`presence_sessions?select=id,samples&app=eq.${encodeURIComponent(a.name)}&started_at=eq.${encodeURIComponent(startedAt)}`)
      if (found.length) {
        await db(`presence_sessions?id=eq.${found[0].id}`, { method: "PATCH", body: JSON.stringify({ ...fields, samples: found[0].samples + 1 }) })
        continue
      }
      await db("presence_sessions", { method: "POST", body: JSON.stringify({ ...fields, activity_type: a.type, app: a.name, application_id: a.application_id || null, started_at: startedAt }) })
      continue
    }
    const since = new Date(now.getTime() - SAME_SESSION_MS).toISOString()
    const open = await db(`presence_sessions?select=id,samples&app=eq.${encodeURIComponent(a.name)}&last_seen_at=gte.${encodeURIComponent(since)}&order=last_seen_at.desc&limit=1`)
    if (open.length) {
      await db(`presence_sessions?id=eq.${open[0].id}`, { method: "PATCH", body: JSON.stringify({ ...fields, samples: open[0].samples + 1 }) })
    } else {
      await db("presence_sessions", { method: "POST", body: JSON.stringify({ ...fields, activity_type: a.type, app: a.name, application_id: a.application_id || null, started_at: now.toISOString() }) })
    }
  }

  console.log(`Recorded ${data.discord_status} with ${activities.length} activit${activities.length === 1 ? "y" : "ies"}.`)
}

// no local .catch: the guard above reports an unhandled rejection to #errors and exits non-zero
await main()
