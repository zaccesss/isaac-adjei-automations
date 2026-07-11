// Checks passport, warranty, API key and card expiry dates in the vault and inventory_items tables and
// posts a Discord alert if anything is due to expire soon. Runs at 08:00 Europe/London (gated in the
// workflow). Node only, no deps.
import { alreadyRanToday } from "./lib/uk-cron.mjs"
import { guard } from "./lib/report-failure.mjs"

guard("vault-expiry-check")

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const webhookUrl = process.env.DISCORD_WEBHOOK_VAULT

const ALERT_DAYS = {
  passport: 90,
  warranty: 30,
  card: 30,
  api_key: 14,
  default: 30,
}

function alertDays(type) {
  return ALERT_DAYS[type] ?? ALERT_DAYS.default
}

function daysUntil(dateStr) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(dateStr)
  target.setHours(0, 0, 0, 0)
  return Math.floor((target.getTime() - today.getTime()) / 86_400_000)
}

function parseCardExpiry(mmyy) {
  const match = mmyy.match(/^(\d{2})\/(\d{2})$/)
  if (!match) return null
  const month = parseInt(match[1], 10)
  const year = 2000 + parseInt(match[2], 10)
  if (month < 1 || month > 12) return null
  const lastDay = new Date(year, month, 0).getDate()
  return `${year}-${String(month).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`
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

async function main() {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    process.exit(1)
  }
  if (!webhookUrl) {
    console.log("DISCORD_WEBHOOK_VAULT not set - skipping (no alert to send)")
    process.exit(0)
  }

  const expiring = []

  const vaultKeys = await supabaseGet("vault?select=name,type,key_expiry&key_expiry=not.is.null")
  for (const row of vaultKeys ?? []) {
    const days = daysUntil(row.key_expiry)
    if (days <= alertDays(row.type ?? "default")) {
      expiring.push({ name: row.name, type: row.type, expiresOn: row.key_expiry, daysLeft: days })
    }
  }

  const vaultCards = await supabaseGet("vault?select=name,type,card_expiry&card_expiry=not.is.null")
  for (const row of vaultCards ?? []) {
    const iso = parseCardExpiry(row.card_expiry)
    if (!iso) continue
    const days = daysUntil(iso)
    if (days <= alertDays("card")) {
      expiring.push({ name: row.name, type: "card", expiresOn: row.card_expiry, daysLeft: days })
    }
  }

  const inventoryItems = await supabaseGet("inventory_items?select=name,category,warranty_expiry&warranty_expiry=not.is.null")
  for (const row of inventoryItems ?? []) {
    const days = daysUntil(row.warranty_expiry)
    if (days <= alertDays("warranty")) {
      expiring.push({ name: row.name, type: row.category ?? "item", expiresOn: row.warranty_expiry, daysLeft: days })
    }
  }

  if (expiring.length === 0) {
    console.log("No expiring items found - nothing to send")
    process.exit(0)
  }

  expiring.sort((a, b) => a.daysLeft - b.daysLeft)
  console.log(`Found ${expiring.length} expiring item(s):`)
  expiring.forEach((i) => console.log(`  ${i.name} (${i.type}): ${i.daysLeft}d - ${i.expiresOn}`))

  const fields = expiring.map((item) => ({
    name: `${item.name} (${item.type})`,
    value:
      item.daysLeft < 0
        ? `Expired ${Math.abs(item.daysLeft)}d ago - ${item.expiresOn}`
        : item.daysLeft === 0
        ? `Expires today - ${item.expiresOn}`
        : `Expires in ${item.daysLeft}d - ${item.expiresOn}`,
    inline: false,
  }))

  const colour = expiring.some((i) => i.daysLeft <= 7) ? 0xe74c3c : 0xf39c12

  // Belt-and-braces: a run that GitHub delayed into the target hour cannot double-post (FORCE bypasses).
  if (await alreadyRanToday("vault-expiry")) {
    console.log("Vault expiry alert already sent today - skipping.")
    process.exit(0)
  }

  const res = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      embeds: [
        {
          title: `Expiry Alert - ${expiring.length} item${expiring.length === 1 ? "" : "s"} expiring soon`,
          color: colour,
          fields,
          footer: { text: "Vault" },
          timestamp: new Date().toISOString(),
        },
      ],
    }),
  })

  if (!res.ok) {
    console.error(`Discord webhook failed: ${res.status} ${res.statusText}`)
    process.exit(1)
  }

  console.log("Discord alert sent successfully")
}

main()
