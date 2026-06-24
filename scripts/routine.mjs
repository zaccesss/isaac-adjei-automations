// Posts a morning habit and streak checklist to a Discord channel webhook. It reads the day's state
// straight from the database over its REST API (service-role key), so it stays a generic "read a
// database, post a summary" job. Node only, no dependencies (global fetch).
//
// It is scheduled from two crons either side of the hour so it can correct for British Summer Time:
// it only posts when it is actually 07:00 in Europe/London and exits quietly otherwise. A manual run
// (workflow_dispatch sets FORCE=1) always posts, for testing.

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const webhook = process.env.DISCORD_WEBHOOK_ROUTINE
const TARGET_HOUR = 7

if (!SUPABASE_URL || !SERVICE_KEY || !webhook) {
  console.error("Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and DISCORD_WEBHOOK_ROUTINE.")
  process.exit(1)
}

// Collapse the two UTC crons to a single 07:00 Europe/London send, unless forced (manual test run).
if (process.env.FORCE !== "1") {
  const part = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", hour12: false })
    .formatToParts(new Date())
    .find((p) => p.type === "hour")
  const londonHour = parseInt(part?.value ?? "99", 10) % 24
  if (londonHour !== TARGET_HOUR) {
    console.log(`London hour is ${londonHour}, not ${TARGET_HOUR} - skipping.`)
    process.exit(0)
  }
}

const today = new Date().toLocaleDateString("en-CA", { timeZone: "Europe/London" })

async function db(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()} (${path})`)
  return res.json()
}

const [habits, habitLogs, streaks, streakLogs] = await Promise.all([
  db("habits?select=id,name&active=eq.true&order=name"),
  db(`habit_logs?select=habit_id&date=eq.${today}`),
  db("streaks?select=id,name&active=eq.true&order=order_index"),
  db(`streak_logs?select=streak_id&date=eq.${today}`),
])

const habitDone = new Set(habitLogs.map((l) => l.habit_id))
const streakDone = new Set(streakLogs.map((l) => l.streak_id))
const line = (name, done) => `${done ? "✅" : "⬜"} ${name}`
const habitList = habits.length ? habits.map((h) => line(h.name, habitDone.has(h.id))).join("\n") : "_none set_"
const streakList = streaks.length ? streaks.map((s) => line(s.name, streakDone.has(s.id))).join("\n") : "_none set_"

const content = [
  "☀️ **Good morning - today's checklist**",
  "",
  "**Habits**",
  habitList,
  "",
  "**Streaks**",
  streakList,
  "",
  "Mark them off with `/habit done`, `/streak log`, or on the dashboard.",
].join("\n")

const res = await fetch(webhook, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ content }),
})
if (!res.ok) {
  console.error("Discord post failed:", res.status, await res.text())
  process.exit(1)
}
console.log(`Posted checklist: ${habits.length} habits, ${streaks.length} streaks.`)
