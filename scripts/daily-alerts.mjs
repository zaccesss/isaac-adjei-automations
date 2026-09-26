// morning alerts that were missing from the reminder set: university deadlines closing in 7, 3 and 1 days (and today) and
// library books due back in 3, 1 or 0 days or already overdue. Each section posts to its own
// webhook and is skipped when that webhook is not set, so a channel can be added without touching the others. Node only.
import { alreadyRanToday, londonDate } from "./lib/uk-cron.mjs"
import { guard } from "./lib/report-failure.mjs"

guard("daily-alerts")

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const HOOKS = {
  deadlines: process.env.DISCORD_WEBHOOK_DEADLINES,
  library: process.env.DISCORD_WEBHOOK_LIBRARY,
}

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
  process.exit(1)
}

async function get(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } })
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`)
  return res.json()
}

async function post(url, embed) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ embeds: [{ ...embed, timestamp: new Date().toISOString() }] }) })
  if (!res.ok) throw new Error(`Discord webhook failed: ${res.status}`)
}

// whole days from today to a YYYY-MM-DD date, both taken as London calendar days so the maths ignores the clock
function daysUntil(dateStr, today) {
  return Math.round((Date.parse(dateStr.slice(0, 10)) - Date.parse(today)) / 86_400_000)
}

async function deadlines(today) {
  if (!HOOKS.deadlines) return console.log("deadlines: no webhook set, skipping")
  const rows = await get("uni_deadlines?select=title,type,due_date,weight_pct,status&status=in.(not_started,in_progress)&order=due_date.asc&limit=200")
  const due = rows.map((r) => ({ ...r, days: daysUntil(r.due_date, today) })).filter((r) => [0, 1, 3, 7].includes(r.days))
  if (!due.length) return console.log("deadlines: nothing due at a reminder point")
  if (await alreadyRanToday("daily-deadlines")) return console.log("deadlines: already sent today")
  const fields = due.map((r) => ({
    name: r.title,
    value: `${r.days === 0 ? "Due today" : r.days === 1 ? "Due tomorrow" : `Due in ${r.days} days`} (${r.type}${r.weight_pct ? `, ${r.weight_pct}%` : ""})`,
  }))
  await post(HOOKS.deadlines, { title: `Deadlines - ${due.length} coming up`, color: due.some((r) => r.days <= 1) ? 0xe74c3c : 0xf39c12, fields })
  // run logs are public, so only the count is printed
  console.log(`deadlines: sent ${due.length}`)
}

async function library(today) {
  if (!HOOKS.library) return console.log("library: no webhook set, skipping")
  const rows = await get("uni_library_books?select=title,due_date&returned_at=is.null&order=due_date.asc&limit=100")
  const due = rows.map((r) => ({ ...r, days: daysUntil(r.due_date, today) })).filter((r) => r.days <= 3)
  if (!due.length) return console.log("library: nothing due back soon")
  if (await alreadyRanToday("daily-library")) return console.log("library: already sent today")
  const fields = due.map((r) => ({
    name: r.title,
    value: r.days < 0 ? `Overdue by ${Math.abs(r.days)} day${r.days === -1 ? "" : "s"}` : r.days === 0 ? "Due back today" : `Due back in ${r.days} day${r.days === 1 ? "" : "s"}`,
  }))
  await post(HOOKS.library, { title: `Library - ${due.length} book${due.length === 1 ? "" : "s"} to return`, color: due.some((r) => r.days <= 0) ? 0xe74c3c : 0xf39c12, fields })
  console.log(`library: sent ${due.length}`)
}

const today = londonDate()
// one section failing must not stop the others, so each runs on its own and the first error is rethrown at the end
const errors = []
for (const step of [() => deadlines(today), () => library(today)]) {
  try {
    await step()
  } catch (e) {
    errors.push(e)
    console.error(e.message)
  }
}
if (errors.length) throw errors[0]
