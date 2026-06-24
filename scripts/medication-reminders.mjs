// Sends due medication reminders. Runs every 30 minutes: for each active reminder within its date range
// it fires any time that has just come due (a 30-minute window absorbs cron jitter), to Discord, email or
// SMS. Each send is logged so a dose is never sent twice and adherence can be charted. Node only, no deps.

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const discordWebhook = process.env.DISCORD_WEBHOOK_REMINDERS
const resendKey = process.env.RESEND_API_KEY
const fromEmail = process.env.REMINDER_FROM_EMAIL || "Medication Reminder <hello@isaacadjei.me>"
const WINDOW = 30 // minutes - how far back a just-due time still counts, to absorb cron delays
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
const today = now.toLocaleDateString("en-CA", { timeZone: TZ }) // YYYY-MM-DD local

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

async function sendEmail(r, t) {
  if (!resendKey || !r.recipient) return false
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
    body: JSON.stringify({ from: fromEmail, to: r.recipient, subject, html, text }),
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

const reminders = await db("medication_reminders?select=*&active=eq.true")
let sent = 0

for (const r of reminders) {
  if (r.start_date && today < r.start_date) continue
  if (r.end_date && today > r.end_date) continue
  for (const t of r.times || []) {
    const tMin = toMin(t)
    // Due if the time falls in the window ending now.
    if (!(tMin <= nowMin && tMin > nowMin - WINDOW)) continue
    // Skip if this reminder + time has already gone out today.
    const dup = await db(`medication_doses?select=id&reminder_id=eq.${r.id}&scheduled_time=eq.${encodeURIComponent(t)}&sent_at=gte.${today}T00:00:00`)
    if (dup && dup.length > 0) continue

    const body = [
      `\u{1F48A} ${r.name}${r.label ? ` - ${r.label}` : ""}`,
      r.dose ? `Dose: ${r.dose}` : "",
      `Time: ${t}`,
      r.notes || "",
    ]
      .filter(Boolean)
      .join("\n")

    let ok = false
    if (r.channel === "discord") ok = await sendDiscord(`\u{1F48A} **${r.name}**${r.label ? ` - ${r.label}` : ""}\n${[r.dose ? `Dose: ${r.dose}` : "", `Time: ${t}`, r.notes || ""].filter(Boolean).join("\n")}`)
    else if (r.channel === "email") ok = await sendEmail(r, t)
    else if (r.channel === "sms") ok = await sendSms(r.recipient, body)

    if (ok) {
      await db("medication_doses", {
        method: "POST",
        body: JSON.stringify({ reminder_id: r.id, label: r.label, name: r.name, channel: r.channel, scheduled_time: t, status: "sent" }),
      })
      sent++
      console.log(`sent: ${r.label}/${r.name} @ ${t} via ${r.channel}`)
    } else {
      console.log(`not sent (channel unconfigured or failed): ${r.label}/${r.name} @ ${t} via ${r.channel}`)
    }
  }
}

console.log(`Done at ${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")} ${TZ}. ${sent} reminder(s) sent.`)
