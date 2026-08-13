// Populates control_job_runs and control_check_snapshots (isaac-adjei-portfolio migration 048), so
// the dashboard's /dashboard/ops page can chart real historical trends. Neither GitHub's Actions API
// (last 30 runs per workflow here, no stored history) nor Healthchecks (current status only) can
// answer a "how healthy was this over the last year" query on their own - this snapshots both
// every time it runs. No retention pruning: this data is small (short rows, no blobs), so nothing
// is ever deleted - each 15-minute sync only needs the last 30 runs to catch whatever is new since
// the previous cycle, the accumulated history underneath just keeps growing. A one-time backfill
// (see backfill-control-history.mjs) seeds deeper history than a fresh sync would ever see on its
// own, since GitHub's own API and Healthchecks' pings endpoint both cap how far back a single call
// can look. Reads the job list from the portfolio's own CONTROL_JOBS via its control-jobs route, so
// this script never keeps its own copy that could drift. Node only, no deps.

import { guard } from "./lib/report-failure.mjs"

guard("control-status-sync")

const PAT = process.env.GH_PAT
const CRON_SECRET = process.env.CRON_SECRET
const PORTFOLIO_URL = process.env.PORTFOLIO_URL || "https://isaacadjei.me"
const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const HC_AUTOMATIONS_KEY = process.env.HEALTHCHECKS_API_KEY
const HC_FLEET_KEY = process.env.HEALTHCHECKS_FLEET_API_KEY
const HC_PORTFOLIO_KEY = process.env.HEALTHCHECKS_PORTFOLIO_API_KEY

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

async function fetchRuns(repo, workflow) {
  try {
    const res = await fetch(
      `https://api.github.com/repos/zaccesss/${repo}/actions/workflows/${workflow}/runs?per_page=30&exclude_pull_requests=true`,
      { headers: { Authorization: `Bearer ${PAT}`, Accept: "application/vnd.github+json" } },
    )
    if (!res.ok) return []
    const data = await res.json()
    return (data.workflow_runs ?? []).map((r) => {
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
    })
  } catch {
    return []
  }
}

async function fetchChecks(key, project) {
  if (!key) return []
  try {
    const res = await fetch("https://healthchecks.io/api/v3/checks/", { headers: { "X-Api-Key": key } })
    if (!res.ok) return []
    const data = await res.json()
    return (data.checks ?? []).map((c) => ({
      hc_slug: c.slug ?? (c.name ?? "").toLowerCase().replace(/\s+/g, "-"),
      project,
      status: c.status ?? "unknown",
      last_ping: c.last_ping ?? null,
    }))
  } catch {
    return []
  }
}

async function upsert(table, rows, onConflict) {
  if (!rows.length) return
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?on_conflict=${onConflict}`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      // A run's status/conclusion changes as it completes, so an in-progress run seen on an earlier
      // sync must be updated here, not just ignored the way Spotify's insert-only history is.
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
    const runs = await fetchRuns(job.repo, job.workflow)
    for (const r of runs) runRows.push({ job_id: job.id, ...r })
  }
  await upsert("control_job_runs", runRows, "job_id,github_run_id")

  const [autoChecks, fleetChecks, portfolioChecks] = await Promise.all([
    fetchChecks(HC_AUTOMATIONS_KEY, "automations"),
    fetchChecks(HC_FLEET_KEY, "fleet"),
    fetchChecks(HC_PORTFOLIO_KEY, "portfolio"),
  ])
  const allChecks = [...autoChecks, ...fleetChecks, ...portfolioChecks]
  await upsert("control_check_snapshots", allChecks, "hc_slug,checked_at")

  console.log(`Synced ${runRows.length} runs across ${jobs.length} jobs, ${allChecks.length} check snapshots.`)
}

// No local .catch: a throw here becomes an unhandled rejection, which the guard above reports in full
// to #errors and then exits non-zero. A local catch would swallow it and the failure would only ever
// reach the run log.
await main()
