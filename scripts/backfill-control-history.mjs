// One-time (or re-runnable) deep backfill for control_job_runs and control_check_snapshots, going
// further back than the regular 15-minute sync ever sees on its own: GitHub's Actions API is paged
// here instead of capped at the last 30. Healthchecks' pings endpoint (up to 100 events per
// check on the free plan) is replayed into snapshot rows. Safe to re-run - everything upserts the
// same way the regular sync does, nothing is ever duplicated or lost. Not scheduled: workflow_dispatch
// only, run by hand when there is a real gap to fill (a fresh CONTROL_JOBS entry, a wiped table).
//
// Healthchecks' pings endpoint records self-reported success/fail events, not silent missed
// check-ins (a check going "down" from simply never pinging leaves no ping record at all), so this
// under-counts real downtime compared to the regular sync's own live status reads - a best-effort
// deepening of history, not a perfect reconstruction.

import { guard } from "./lib/report-failure.mjs"

guard("backfill-control-history")

const PAT = process.env.GH_PAT
const CRON_SECRET = process.env.CRON_SECRET
const PORTFOLIO_URL = process.env.PORTFOLIO_URL || "https://isaacadjei.me"
const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const HC_AUTOMATIONS_KEY = process.env.HEALTHCHECKS_API_KEY
const HC_FLEET_KEY = process.env.HEALTHCHECKS_FLEET_API_KEY
const HC_PORTFOLIO_KEY = process.env.HEALTHCHECKS_PORTFOLIO_API_KEY

// A generous ceiling against runaway pagination on a job with an unusually long run history.
const MAX_PAGES = 20

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!PAT || !CRON_SECRET) {
  console.log("GH_PAT or CRON_SECRET not set - skipping.")
  process.exit(0)
}

async function retry(fn, attempts = 3) {
  let lastErr
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn()
    } catch (e) {
      lastErr = e
      if (i < attempts - 1) await new Promise((r) => setTimeout(r, 1000 * (i + 1)))
    }
  }
  throw lastErr
}

async function fetchJobs() {
  const res = await retry(async () => {
    const r = await fetch(`${PORTFOLIO_URL}/api/dashboard/control-jobs`, {
      headers: { Authorization: `Bearer ${CRON_SECRET}` },
    })
    if (!r.ok) throw new Error(`control-jobs ${r.status} ${await r.text()}`)
    return r
  })
  return (await res.json()).jobs
}

function mapRun(r) {
  const started = r.run_started_at ?? r.created_at
  const done = r.status === "completed"
  return {
    github_run_id: r.id,
    conclusion: r.conclusion,
    status: r.status,
    started_at: started,
    duration_s: done ? Math.max(0, Math.round((new Date(r.updated_at).getTime() - new Date(started).getTime()) / 1000)) : null,
    url: r.html_url,
  }
}

async function fetchAllRuns(repo, workflow) {
  const runs = []
  for (let page = 1; page <= MAX_PAGES; page++) {
    let batch
    try {
      const res = await fetch(
        `https://api.github.com/repos/zaccesss/${repo}/actions/workflows/${workflow}/runs?per_page=100&page=${page}&exclude_pull_requests=true`,
        { headers: { Authorization: `Bearer ${PAT}`, Accept: "application/vnd.github+json" } },
      )
      if (!res.ok) break
      batch = (await res.json()).workflow_runs ?? []
    } catch {
      break
    }
    if (!batch.length) break
    runs.push(...batch)
    if (batch.length < 100) break
  }
  return runs.map(mapRun)
}

async function fetchAllPings(key, uuid) {
  try {
    const res = await fetch(`https://healthchecks.io/api/v3/checks/${uuid}/pings/`, { headers: { "X-Api-Key": key } })
    if (!res.ok) return []
    return (await res.json()).pings ?? []
  } catch {
    return []
  }
}

async function fetchChecksWithHistory(key, project) {
  if (!key) return []
  let checks
  try {
    const res = await fetch("https://healthchecks.io/api/v3/checks/", { headers: { "X-Api-Key": key } })
    if (!res.ok) return []
    checks = (await res.json()).checks ?? []
  } catch {
    return []
  }
  const rows = []
  for (const c of checks) {
    const slug = c.slug ?? (c.name ?? "").toLowerCase().replace(/\s+/g, "-")
    const pings = await fetchAllPings(key, c.uuid)
    for (const p of pings) {
      // Only success/fail pings map to a real status snapshot - "start" just marks work beginning,
      // not a health state.
      const status = p.type === "success" ? "up" : p.type === "fail" ? "down" : null
      if (!status) continue
      rows.push({ hc_slug: slug, project, status, last_ping: p.date, checked_at: p.date })
    }
  }
  return rows
}

async function upsert(table, rows, onConflict) {
  if (!rows.length) return
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?on_conflict=${onConflict}`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates",
    },
    body: JSON.stringify(rows),
  })
  if (!res.ok) throw new Error(`${table} upsert ${res.status} ${await res.text()}`)
}

async function main() {
  const jobs = await fetchJobs()
  if (!jobs?.length) throw new Error("control-jobs returned no jobs")

  const runRows = []
  for (const job of jobs) {
    const runs = await fetchAllRuns(job.repo, job.workflow)
    console.log(`  ${job.id}: ${runs.length} runs`)
    for (const r of runs) runRows.push({ job_id: job.id, ...r })
  }
  await upsert("control_job_runs", runRows, "job_id,github_run_id")

  const [autoSnaps, fleetSnaps, portfolioSnaps] = await Promise.all([
    fetchChecksWithHistory(HC_AUTOMATIONS_KEY, "automations"),
    fetchChecksWithHistory(HC_FLEET_KEY, "fleet"),
    fetchChecksWithHistory(HC_PORTFOLIO_KEY, "portfolio"),
  ])
  const allSnaps = [...autoSnaps, ...fleetSnaps, ...portfolioSnaps]
  await upsert("control_check_snapshots", allSnaps, "hc_slug,checked_at")

  console.log(`Backfilled ${runRows.length} runs across ${jobs.length} jobs, ${allSnaps.length} check-status snapshots.`)
}

await main()
