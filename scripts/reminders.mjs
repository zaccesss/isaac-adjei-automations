// Sends one-off appointment, meeting and general reminders from the reminders table. Runs every 30
// minutes: each reminder can have several lead times (a week before and a day before, say), and each fires
// once when its moment arrives, to any of Discord, email and SMS. sent_leads records which lead times have
// gone out so none repeats, and reminded_at is stamped once every lead has fired or the event has passed, so
// the row drops out of the scan. Because event_at is an absolute timestamp there is no local-hour handling to
// do, unlike the recurring medication reminders. Node only, no deps.
//
// A workflow_dispatch with TEST_EMAIL or TEST_TO set sends one test message there and exits.

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const discordWebhook = process.env.DISCORD_WEBHOOK_REMINDERS
const resendKey = process.env.RESEND_API_KEY
const fromEmail = process.env.REMINDER_FROM_EMAIL || "Reminders <hello@isaacadjei.me>"
const TZ = "Europe/London"

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}

async function db(path, opts) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}`, "Content-Type": "application/json", ...(opts?.headers || {}) },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()} (${path})`)
  return res.status === 204 ? null : res.json()
}

const patch = (id, body) =>
  db(`reminders?id=eq.${id}`, { method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify(body) })

const KIND_LABEL = { appointment: "Appointment", meeting: "Meeting", other: "Reminder" }
const KIND_EMOJI = { appointment: "\u{1F5D3}\u{FE0F}", meeting: "\u{1F465}", other: "\u{1F514}" }

function fmtWhen(iso) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso))
}

// The actual time from now until the event, so the message is right even when the send runs later than the
// configured lead (a reminder added at the last minute or a delayed cron). Rounded to a friendly unit.
function humanUntil(ms) {
  const min = Math.round(ms / 60000)
  if (min <= 1) return "now"
  if (min < 90) return `in ${min} minutes`
  const hours = Math.round(min / 60)
  if (hours < 36) return `in ${hours} hour${hours === 1 ? "" : "s"}`
  const days = Math.round(hours / 24)
  if (days < 14) return `in ${days} day${days === 1 ? "" : "s"}`
  return `in ${Math.round(days / 7)} week${Math.round(days / 7) === 1 ? "" : "s"}`
}

async function sendDiscord(content) {
  if (!discordWebhook) return false
  const res = await fetch(discordWebhook, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) })
  return res.ok
}

async function sendEmail(to, r) {
  if (!resendKey || !to) return false
  const kindLabel = KIND_LABEL[r.kind] || "Reminder"
  const when = fmtWhen(r.event_at)
  const until = humanUntil(new Date(r.event_at).getTime() - Date.now())
  const emoji = KIND_EMOJI[r.kind] || "\u{1F514}"
  const subject = `${kindLabel} reminder: ${r.title} - ${when}`
  const html = [
    `<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;color:#111">`,
    `<h2 style="margin:0 0 12px">${emoji} ${kindLabel} ${until}</h2>`,
    `<p style="font-size:18px;font-weight:600;margin:0 0 6px">${r.title}</p>`,
    `<p style="font-size:16px;color:#555;margin:0 0 6px">When: ${when}</p>`,
    r.location ? `<p style="font-size:16px;color:#555;margin:0 0 6px">Where: ${r.location}</p>` : "",
    r.notes ? `<p style="font-size:14px;color:#777;margin:8px 0 0">${r.notes}</p>` : "",
    `<hr style="border:none;border-top:1px solid #eee;margin:16px 0" />`,
    `<p style="font-size:12px;color:#999">Automated reminder.</p>`,
    `</div>`,
  ].join("")
  const text = [`${kindLabel} ${until}.`, ``, r.title, `When: ${when}`, r.location ? `Where: ${r.location}` : "", r.notes || ""].filter(Boolean).join("\n")
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${resendKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: fromEmail, to, subject, html, text }),
  })
  if (!res.ok) console.error("resend:", res.status, await res.text())
  return res.ok
}

async function sendSms(to, body) {
  const sid = process.env.TWILIO_ACCOUNT_SID
  const token = process.env.TWILIO_AUTH_TOKEN
  const from = process.env.TWILIO_FROM_NUMBER
  if (!sid || !token || !from || !to) {
    console.log("SMS not configured (need TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER and a phone) - skipping.")
    return false
  }
  const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${sid}:${token}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ To: to, From: from, Body: body }),
  })
  if (!res.ok) console.error("twilio:", res.status, await res.text())
  return res.ok
}

// Manual test path: a workflow_dispatch with TEST_EMAIL or TEST_TO sends one test message and exits.
if (process.env.TEST_EMAIL || process.env.TEST_TO) {
  if (process.env.TEST_EMAIL) {
    const ok = await sendEmail(process.env.TEST_EMAIL, {
      kind: "appointment",
      title: "Test reminder",
      event_at: new Date(Date.now() + 86400000).toISOString(),
      location: "Nowhere",
      notes: "If you got this, email reminders are working.",
    })
    console.log(ok ? `Test email sent to ${process.env.TEST_EMAIL}.` : "Test email failed - check RESEND_API_KEY and the from address.")
  }
  if (process.env.TEST_TO) {
    const ok = await sendSms(process.env.TEST_TO, "Test from your reminders system. If you received this, SMS is working.")
    console.log(ok ? `Test SMS sent to ${process.env.TEST_TO}.` : "Test SMS failed - check the Twilio secrets and sender.")
  }
  process.exit(0)
}

const now = Date.now()
const rows = await db("reminders?select=*&active=eq.true&reminded_at=is.null")
let sent = 0

for (const r of rows) {
  const eventMs = new Date(r.event_at).getTime()
  if (Number.isNaN(eventMs)) continue

  const leads = Array.isArray(r.lead_minutes) && r.lead_minutes.length ? r.lead_minutes : [1440]
  const sentLeads = new Set(Array.isArray(r.sent_leads) ? r.sent_leads : [])
  const channels = Array.isArray(r.channels) && r.channels.length ? r.channels : ["discord"]

  // Lead times whose moment has arrived but which have not fired yet.
  const dueUnfired = leads.filter((l) => !sentLeads.has(l) && now >= eventMs - l * 60000).sort((a, b) => a - b)
  if (dueUnfired.length === 0) continue

  // Fire only the most imminent due lead (smallest = closest to the event). Any larger leads that are also
  // due at the same time are stale (their moment passed, a nearer reminder is going out now), so I mark them
  // fired without notifying rather than sending a burst of near-identical messages. This only happens when a
  // reminder is added late or the job was down; normally each lead fires alone as its moment arrives.
  const toFire = dueUnfired[0]
  const toSkip = dueUnfired.slice(1)

  const emoji = KIND_EMOJI[r.kind] || "\u{1F514}"
  const kindLabel = KIND_LABEL[r.kind] || "Reminder"
  const when = fmtWhen(r.event_at)

  let firedOk = false
  if (now <= eventMs) {
    const until = humanUntil(eventMs - now)
    const lines = [`When: ${when}`, r.location ? `Where: ${r.location}` : "", r.notes || ""].filter(Boolean).join("\n")
    const discordBody = `${emoji} **${kindLabel}: ${r.title}** ${until}\n${lines}`
    const smsBody = [`${kindLabel} ${until}: ${r.title}`, `When: ${when}`, r.location ? `Where: ${r.location}` : ""].filter(Boolean).join("\n")
    if (channels.includes("discord")) firedOk = (await sendDiscord(discordBody)) || firedOk
    if (channels.includes("email")) firedOk = (await sendEmail(r.email, r)) || firedOk
    if (channels.includes("sms")) firedOk = (await sendSms(r.phone, smsBody)) || firedOk
    if (firedOk) {
      sentLeads.add(toFire)
      sent++
      console.log(`sent ${r.kind}: ${r.title} @ ${when} (lead ${toFire}m) via ${channels.join(",")}`)
    } else {
      console.log(`not sent (no channel succeeded): ${r.kind} "${r.title}" lead ${toFire}m`)
    }
  } else {
    // The event is already in the past: mark this lead fired without notifying.
    sentLeads.add(toFire)
  }
  for (const l of toSkip) sentLeads.add(l)

  const allDone = leads.every((l) => sentLeads.has(l))
  // Persist progress when something changed. A transient send failure before the event leaves toFire unfired
  // (and reminded_at null), so the next run retries it.
  if (firedOk || toSkip.length > 0 || now > eventMs) {
    const body = { sent_leads: [...sentLeads] }
    if (allDone || now > eventMs) body.reminded_at = new Date().toISOString()
    await patch(r.id, body)
  }
}

console.log(`Done. ${sent} reminder(s) sent.`)
