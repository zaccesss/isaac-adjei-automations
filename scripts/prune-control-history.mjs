// deletes Ops history older than KEEP_DAYS from control_job_runs and control_check_snapshots. Both tables gain rows on
// every sync and are kept forever otherwise, which made them close to half the database. The Ops charts only need
// recent history, so a year view simply starts at the cut-off. Set DRY_RUN=1 to report counts without deleting. Node only.
import { guard } from "./lib/report-failure.mjs"

guard("prune-control-history")

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const KEEP_DAYS = Number(process.env.KEEP_DAYS || 90)
const DRY_RUN = process.env.DRY_RUN === "1"

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
  process.exit(1)
}
if (!Number.isFinite(KEEP_DAYS) || KEEP_DAYS < 30) {
  // a typo in the variable must never wipe recent history
  console.error("KEEP_DAYS must be a number of at least 30")
  process.exit(1)
}

const headers = { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` }
const cutoff = new Date(Date.now() - KEEP_DAYS * 86_400_000).toISOString()
const TABLES = [
  { table: "control_job_runs", column: "started_at" },
  { table: "control_check_snapshots", column: "checked_at" },
]

async function count(table, column) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${column}=lt.${cutoff}&select=*`, {
    method: "HEAD",
    headers: { ...headers, Prefer: "count=exact" },
  })
  if (!res.ok) throw new Error(`Supabase ${res.status} counting ${table}`)
  return Number(res.headers.get("content-range")?.split("/")[1] ?? 0)
}

for (const { table, column } of TABLES) {
  const old = await count(table, column)
  if (DRY_RUN || old === 0) {
    console.log(`${table}: ${old} rows older than ${KEEP_DAYS} days${DRY_RUN ? " (dry run, nothing deleted)" : ""}`)
    continue
  }
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${column}=lt.${cutoff}`, { method: "DELETE", headers })
  if (!res.ok) throw new Error(`Supabase ${res.status} deleting from ${table}: ${await res.text()}`)
  console.log(`${table}: deleted ${old} rows older than ${KEEP_DAYS} days`)
}
