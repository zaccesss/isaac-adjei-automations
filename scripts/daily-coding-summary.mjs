// Posts the daily Discord coding recap for the day that just ended (runs 00:30 Europe/London),
// comparing that day's coding time to the 30-day average, read from the wakatime_daily table. The
// upstream WakaTime sync runs first in the same workflow, so the day is fully settled. Node only.
import { londonDate, alreadyRanToday } from "./lib/uk-cron.mjs"

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const DISCORD_WEBHOOK = process.env.DISCORD_WEBHOOK_CODING

if (!SUPABASE_URL || !SUPABASE_KEY || !DISCORD_WEBHOOK) {
  console.log("Missing env vars - skipping.")
  process.exit(0)
}

function fmt(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

async function supabaseGet(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
    },
  })
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`)
  return res.json()
}

// The day that just ended, in UK local time (this runs at 00:30 Europe/London).
const targetDay = londonDate(new Date(Date.now() - 24 * 60 * 60 * 1000))
const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)

const rows = await supabaseGet(
  `wakatime_daily?select=date,total_seconds&date=gte.${thirtyDaysAgo}&order=date.desc`
)

const dayRow = rows.find((r) => r.date === targetDay)
const daySeconds = dayRow?.total_seconds ?? 0

if (daySeconds === 0) {
  console.log(`No coding on ${targetDay} - skipping Discord notification.`)
  process.exit(0)
}

const activeDays = rows.filter((r) => r.date !== targetDay && r.total_seconds > 0)
const avgSeconds =
  activeDays.length > 0
    ? Math.round(activeDays.reduce((sum, r) => sum + r.total_seconds, 0) / activeDays.length)
    : 0

const aboveAverage = avgSeconds > 0 && daySeconds > avgSeconds
const diff = Math.abs(daySeconds - avgSeconds)
const pct = avgSeconds > 0 ? Math.round((diff / avgSeconds) * 100) : 0

let emoji = "\u{1F4BB}"
let headline = `Coded for **${fmt(daySeconds)}**`
if (aboveAverage) {
  emoji = pct >= 50 ? "\u{1F525}" : "✅"
  headline += ` - ${pct}% above the 30-day average (${fmt(avgSeconds)})`
} else if (avgSeconds > 0) {
  headline += ` - ${pct}% below the 30-day average (${fmt(avgSeconds)})`
}

const payload = {
  content: null,
  embeds: [
    {
      title: `${emoji} Daily coding summary - ${targetDay}`,
      description: headline,
      color: aboveAverage ? 0x22c55e : 0x6366f1,
      footer: { text: "WakaTime" },
    },
  ],
}

// Belt-and-braces: a run that GitHub delayed into the target hour cannot double-post (FORCE bypasses).
if (await alreadyRanToday("coding-summary")) {
  console.log("Coding summary already sent today - skipping.")
  process.exit(0)
}

const res = await fetch(DISCORD_WEBHOOK, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload),
})

if (!res.ok) {
  console.error("Discord webhook failed:", res.status, await res.text())
  process.exit(1)
}

console.log("Discord summary sent:", headline)
