// Posts a habit and streak checklist to a Discord channel webhook, twice a day: the full morning
// checklist at 07:00 Europe/London and a smart evening pass at 20:00 that only chases what is still
// unlogged (and stays silent when everything is done). It reads the day's state straight from the
// database over its REST API (service-role key), so it stays a generic "read a database, post a
// summary" job. Node only, no dependencies (global fetch).
//
// The workflow fires across both windows either side of the hour to ride out British Summer Time
// and GitHub's cron slop; each slot posts once and claims (job-slot, UK-day). A manual run can pick
// its slot with the SLOT input, and FORCE=1 always posts, for testing.

import { londonHour, alreadyRanToday } from "./lib/uk-cron.mjs"
import { guard } from "./lib/report-failure.mjs"

guard("routine")

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const webhook = process.env.DISCORD_WEBHOOK_ROUTINE
const MORNING_HOUR = 7
const EVENING_HOUR = 20

if (!SUPABASE_URL || !SERVICE_KEY || !webhook) {
  console.error("Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and DISCORD_WEBHOOK_ROUTINE.")
  process.exit(1)
}

// am is the full morning checklist; pm is the evening pass that only chases what is still unlogged.
// An explicit SLOT (a manual run or a dispatcher) wins; otherwise the London hour decides.
const slot = process.env.SLOT === "am" || process.env.SLOT === "pm" ? process.env.SLOT : londonHour() < 12 ? "am" : "pm"

// GitHub Actions cron is unreliable (it delays and drops runs), so the workflow fires every 30 min
// across each window. Post once per slot, on the first run inside the window, and claim
// (job-slot, UK-day) so a later run in the window never repeats it. A manual run (FORCE=1) always
// posts, for testing.
if (process.env.FORCE !== "1") {
  const h = londonHour()
  const [from, to] = slot === "am" ? [MORNING_HOUR, MORNING_HOUR + 2] : [EVENING_HOUR, EVENING_HOUR + 2]
  if (h < from || h > to) {
    console.log(`London hour is ${h}, outside the ${slot} window ${from}-${to} - skipping.`)
    process.exit(0)
  }
  if (await alreadyRanToday(`routine-${slot}`)) {
    console.log(`Already posted the ${slot} checklist today - skipping.`)
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
const pendingHabits = habits.filter((h) => !habitDone.has(h.id))
const pendingStreaks = streaks.filter((s) => !streakDone.has(s.id))

// The evening pass only chases what is left; when everything is logged it stays silent.
if (slot === "pm" && pendingHabits.length === 0 && pendingStreaks.length === 0) {
  console.log("Evening pass: everything is already logged - nothing to post.")
  process.exit(0)
}

const line = (name, done) => `${done ? "✅" : "⬜"} ${name}`
let content
if (slot === "am") {
  const habitList = habits.length ? habits.map((h) => line(h.name, habitDone.has(h.id))).join("\n") : "_none set_"
  const streakList = streaks.length ? streaks.map((s) => line(s.name, streakDone.has(s.id))).join("\n") : "_none set_"
  content = [
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
} else {
  const sections = []
  if (pendingHabits.length) sections.push("**Habits**", pendingHabits.map((h) => line(h.name, false)).join("\n"), "")
  if (pendingStreaks.length) sections.push("**Streaks**", pendingStreaks.map((s) => line(s.name, false)).join("\n"), "")
  content = [
    "🌙 **Evening check - still unlogged today**",
    "",
    ...sections,
    "There is still time - mark them off with `/habit done`, `/streak log`, or on the dashboard.",
  ].join("\n")
}

const res = await fetch(webhook, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ content }),
})
if (!res.ok) {
  console.error("Discord post failed:", res.status, await res.text())
  process.exit(1)
}
console.log(
  slot === "am"
    ? `Posted the morning checklist: ${habits.length} habits, ${streaks.length} streaks.`
    : `Posted the evening pass: ${pendingHabits.length} habits, ${pendingStreaks.length} streaks still unlogged.`,
)
