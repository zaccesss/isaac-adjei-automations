// Sends due medication reminders. Runs every 30 minutes: for each active reminder within its date range
// it fires any time that has just come due (a 30-minute window absorbs cron jitter), to any of its
// channels - Discord, email, SMS - and it can use several at once. Each due time is logged once so a dose
// is never sent twice and adherence can be charted. Node only, no deps.
//
// A workflow_dispatch with TEST_TO set sends one test SMS to that number and exits.

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const discordWebhook = process.env.DISCORD_WEBHOOK_REMINDERS
const resendKey = process.env.RESEND_API_KEY
const fromEmail = process.env.REMINDER_FROM_EMAIL || "Medication Reminder <hello@isaacadjei.me>"
const WINDOW = 30
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
  return res.status === 204 ? null : res.json()
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
  if (!res.ok) console.error("resend:", res.status, await res.text())
  return res.ok
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
  if (!res.ok) console.error("twilio:", res.status, await res.text())
  return res.ok
}

// Manual test path: a workflow_dispatch with TEST_TO set sends one SMS and exits.
if (process.env.TEST_TO) {
  const ok = await sendSms(process.env.TEST_TO, "Test from your medication reminder system. If you received this, SMS is working.")
  console.log(ok ? `Test SMS sent to ${process.env.TEST_TO}.` : "Test SMS failed - check the Twilio secrets and sender.")
  process.exit(ok ? 0 : 1)
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
    if (!(tMin <= nowMin && tMin > nowMin - WINDOW)) continue
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
      console.log(`sent: ${r.label}/${r.name} @ ${t} via ${channels.join(",")}`)
    } else {
      console.log(`not sent (no channel succeeded): ${r.label}/${r.name} @ ${t}`)
    }
  }
}

console.log(`Done at ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")} ${TZ}. ${sentDoses} dose(s) sent.`)
