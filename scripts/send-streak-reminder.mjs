// Posts a Discord reminder of which active streaks are not yet logged for today, read from the
// streaks and streak_logs tables: a morning check at 08:00 Europe/London and an evening pass at
// 20:00 that only posts while something is still unlogged (both windows gated in the workflow).
// Node only.
import { alreadyRanToday, londonHour } from "./lib/uk-cron.mjs"
import { guard } from "./lib/report-failure.mjs"

guard("streak-reminder")

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const webhookUrl = process.env.DISCORD_WEBHOOK_STREAKS

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!webhookUrl) {
  console.log("No DISCORD_WEBHOOK_STREAKS set - skipping.")
  process.exit(0)
}

// am is the morning check; pm is the evening chase that stays silent when everything is logged.
// An explicit SLOT (a manual run or a dispatcher) wins; otherwise the London hour decides.
const slot = process.env.SLOT === "am" || process.env.SLOT === "pm" ? process.env.SLOT : londonHour() < 12 ? "am" : "pm"

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

const today = new Date().toISOString().split("T")[0]

const [streaks, logs] = await Promise.all([
  supabaseGet("streaks?select=id,name,icon&active=eq.true&order=order_index"),
  supabaseGet(`streak_logs?select=streak_id&date=eq.${today}&completed=eq.true`),
])

if (!streaks || streaks.length === 0) {
  console.log("No active streaks - nothing to remind.")
  process.exit(0)
}

const doneIds = new Set((logs ?? []).map((l) => l.streak_id))
const pending = streaks.filter((s) => !doneIds.has(s.id))
const done = streaks.filter((s) => doneIds.has(s.id))

// The evening pass only exists to chase what is left; when the day is complete it stays silent
// (the morning check still celebrates a clean slate).
if (slot === "pm" && pending.length === 0) {
  console.log("Evening pass: every streak is logged - nothing to post.")
  process.exit(0)
}

const dateLabel = new Date().toLocaleDateString("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
})

let description
let color
const fields = []

if (pending.length === 0) {
  description = "All streaks done for today - great work! Keep the momentum going. \u{1F389}"
  color = 0x22c55e
} else {
  description =
    slot === "am"
      ? `You have **${pending.length}** streak${pending.length === 1 ? "" : "s"} left to complete today. Don't break the chain!`
      : `**${pending.length}** streak${pending.length === 1 ? " is" : "s are"} still unlogged today - there is still time to keep the chain alive.`
  color = 0xf59e0b
  fields.push({
    name: "Still to do",
    value: pending.map((s) => `${s.icon} ${s.name}`).join("\n"),
    inline: true,
  })
}

if (done.length > 0) {
  fields.push({
    name: done.length === streaks.length ? "All done ✅" : "Completed",
    value: done.map((s) => `${s.icon} ${s.name}`).join("\n"),
    inline: true,
  })
}

const embed = {
  title: slot === "am" ? `☀️ Morning streak check - ${dateLabel}` : `🌙 Evening streak check - ${dateLabel}`,
  description,
  color,
  fields,
  footer: { text: "Streaks" },
  timestamp: new Date().toISOString(),
}

// Belt-and-braces: a run that GitHub delayed into the target window cannot double-post (FORCE
// bypasses). Each slot claims its own day, so the morning and evening checks both send.
if (await alreadyRanToday(`streak-reminder-${slot}`)) {
  console.log(`Streak ${slot} reminder already sent today - skipping.`)
  process.exit(0)
}

const res = await fetch(webhookUrl, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ embeds: [embed] }),
})

if (!res.ok) {
  const text = await res.text()
  console.error("Discord error:", res.status, text)
  process.exit(1)
}

console.log(`Streak ${slot} reminder sent. Pending: ${pending.length}, Done: ${done.length}`)
