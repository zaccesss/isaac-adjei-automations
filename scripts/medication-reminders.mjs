// Sends due medication reminders. Runs every 30 minutes: for each active reminder within its date range
// it fires any time that has just come due (a 30-minute window absorbs cron jitter), to any of its
// channels - Discord, email, SMS - and it can use several at once. Each due time is logged once so a dose
// is never sent twice and adherence can be charted. Node only, no deps.
//
// A workflow_dispatch with TEST_TO set sends one test SMS to that number and exits.

import { guard } from "./lib/report-failure.mjs"

guard("medication-reminders")

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const discordWebhook = process.env.DISCORD_WEBHOOK_REMINDERS
const resendKey = process.env.RESEND_API_KEY
const fromEmail = process.env.REMINDER_FROM_EMAIL || "Medication Reminder <hello@isaacadjei.me>"
const TZ = "Europe/London"

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}

const now = new Date()
const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(now)
const hh = Number(parts.find((p) => p.type === "hour")?.value ?? 0) % 24
const mm = Number(parts.find((p) => p.type === "minute")?.value ?? 0)
const nowMin = hh * 60 + mm
const today = now.toLocaleDateString("en-CA", { timeZone: TZ })

async function db(path, opts) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}`, "Content-Type": "application/json", ...(opts?.headers || {}) },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()} (${path})`)
  // A POST insert returns 201 with an empty body, so parse only when there is one.
  const text = await res.text()
  return text ? JSON.parse(text) : null
}

const toMin = (t) => {
  const [h, m] = String(t).split(":").map(Number)
  return h * 60 + m
}

async function sendDiscord(content) {
  if (!discordWebhook) return false
  const res = await fetch(discordWebhook, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) })
  return res.ok
}

async function sendEmail(to, r, t) {
  if (!resendKey || !to) return false
  const subject = `Medication reminder: ${r.name} at ${t}`
  const html = [
    `<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;color:#111">`,
    `<h2 style="margin:0 0 12px">\u{1F48A} Time for your medication</h2>`,
    `<p style="font-size:18px;font-weight:600;margin:0 0 6px">${r.name}</p>`,
    r.dose ? `<p style="font-size:16px;margin:0 0 6px">${r.dose}</p>` : "",
    `<p style="font-size:16px;color:#555;margin:0 0 6px">Time: ${t}</p>`,
    r.notes ? `<p style="font-size:14px;color:#777;margin:8px 0 0">${r.notes}</p>` : "",
    `<hr style="border:none;border-top:1px solid #eee;margin:16px 0" />`,
    `<p style="font-size:12px;color:#999">Automated reminder. Take care.</p>`,
    `</div>`,
  ].join("")
  const text = [`Time for your medication.`, ``, r.name, r.dose || "", `Time: ${t}`, r.notes || ""].filter(Boolean).join("\n")
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${resendKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: fromEmail, to, subject, html, text }),
  })
  if (!res.ok) console.error("resend:", res.status)
  return res.ok
}

// A due dose that no channel could deliver is a real problem - it is often someone else's medication -
// so I raise it to #errors rather than only logging it. The dose is deliberately NOT logged as sent, so
// the next run retries delivery; this alert makes the failure visible in the meantime. #errors is a
// private channel, so the name is safe to include here, unlike the public run log which stays id-only.
async function alertDeliveryFailure(r, t, channels) {
  const webhook = process.env.DISCORD_WEBHOOK_ERRORS
  if (!webhook) return
  const tried = channels.length ? channels.join(", ") : "no channels configured"
  const content = `\u{1F534} **Medication dose failed to deliver**\n${r.name}${r.label ? ` - ${r.label}` : ""} at ${t}\nTried: ${tried} - all failed. The dose was not logged, so the next run will retry.`
  try {
    await fetch(webhook, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) })
  } catch (e) {
    console.error("could not post medication delivery failure to #errors:", e?.message || e)
  }
}

async function sendSms(to, text) {
  const sid = process.env.TWILIO_ACCOUNT_SID
  const token = process.env.TWILIO_AUTH_TOKEN
  const from = process.env.TWILIO_FROM_NUMBER
  if (!sid || !token || !from || !to) {
    console.log("SMS not configured (need TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER) - skipping.")
    return false
  }
  const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${sid}:${token}`).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ To: to, From: from, Body: text }),
  })
  if (!res.ok) console.error("twilio:", res.status)
  return res.ok
}

// Manual test path: a workflow_dispatch with TEST_EMAIL or TEST_TO sends one test message and exits.
if (process.env.TEST_EMAIL || process.env.TEST_TO) {
  if (process.env.TEST_EMAIL) {
    const ok = await sendEmail(process.env.TEST_EMAIL, { name: "Test reminder", dose: "1 drop - test", notes: "If you got this, email reminders are working." }, "now")
    console.log(ok ? "Test email sent." : "Test email failed - check RESEND_API_KEY and the from address.")
  }
  if (process.env.TEST_TO) {
    const ok = await sendSms(process.env.TEST_TO, "Test from your medication reminder system. If you received this, SMS is working.")
    console.log(ok ? "Test SMS sent." : "Test SMS failed - check the Twilio secrets and sender.")
  }
  process.exit(0)
}

const reminders = await db("medication_reminders?select=*&active=eq.true")
let sentDoses = 0

for (const r of reminders) {
  if (r.start_date && today < r.start_date) continue
  if (r.end_date && today > r.end_date) continue
  // Fall back to the old single channel/recipient for any row not yet migrated.
  const channels = Array.isArray(r.channels) && r.channels.length ? r.channels : r.channel ? [r.channel] : []
  const emailTo = r.email || (r.channel === "email" ? r.recipient : null)
  const phoneTo = r.phone || (r.channel === "sms" ? r.recipient : null)

  for (const t of r.times || []) {
    const tMin = toMin(t)
    // Send any dose whose time has passed today and has not been logged yet. GitHub Actions cron is
    // unreliable - it delays runs and drops many of them - so a fixed match window silently missed doses
    // that fell in the gaps. Catching up on every due-but-unsent dose (deduped below, once per day) means
    // the next run that does fire delivers the reminder, so a dose is never skipped, only ever a bit late.
    if (tMin > nowMin) continue
    const dup = await db(`medication_doses?select=id&reminder_id=eq.${r.id}&scheduled_time=eq.${encodeURIComponent(t)}&sent_at=gte.${today}T00:00:00`)
    if (dup && dup.length > 0) continue

    const smsBody = [`\u{1F48A} ${r.name}${r.label ? ` - ${r.label}` : ""}`, r.dose ? `Dose: ${r.dose}` : "", `Time: ${t}`, r.notes || ""].filter(Boolean).join("\n")
    const discordBody = `\u{1F48A} **${r.name}**${r.label ? ` - ${r.label}` : ""}\n${[r.dose ? `Dose: ${r.dose}` : "", `Time: ${t}`, r.notes || ""].filter(Boolean).join("\n")}`

    let anyOk = false
    if (channels.includes("discord")) anyOk = (await sendDiscord(discordBody)) || anyOk
    if (channels.includes("email")) anyOk = (await sendEmail(emailTo, r, t)) || anyOk
    if (channels.includes("sms")) anyOk = (await sendSms(phoneTo, smsBody)) || anyOk

    if (anyOk) {
      await db("medication_doses", {
        method: "POST",
        body: JSON.stringify({ reminder_id: r.id, label: r.label, name: r.name, channel: channels.join(","), scheduled_time: t, status: "sent" }),
      })
      sentDoses++
      // Run logs are public, so print the row id only - medication names are health data.
      console.log(`sent: reminder ${r.id} @ ${t} via ${channels.join(",")}`)
    } else {
      console.log(`not sent (no channel succeeded): reminder ${r.id} @ ${t}`)
      await alertDeliveryFailure(r, t, channels)
    }
  }
}

console.log(`Done at ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")} ${TZ}. ${sentDoses} dose(s) sent.`)
