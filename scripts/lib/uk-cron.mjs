// Shared UK-time cron helpers for the automations scripts. Node only, no deps.
//
// Neither GitHub Actions nor Vercel observes British Summer Time - crons are always UTC - so each
// time-pinned job fires from TWO crons (a GMT branch and a BST branch, one hour apart). A workflow
// gate step (TZ=Europe/London date) runs the job only at the intended local hour, and message-senders
// additionally claim (job, UK-day) in the cron_runs table so a run that GitHub delayed into the target
// hour cannot double-post. Mirrors the portfolio lib/london-time.ts and the older scripts/routine.mjs.

const DATE_FMT = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }) // en-CA => YYYY-MM-DD

// Today's date in Europe/London as YYYY-MM-DD.
export function londonDate(date = new Date()) {
  return DATE_FMT.format(date)
}

// Current hour (0..23) in Europe/London.
export function londonHour(date = new Date()) {
  const h = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", hour12: false }).format(date)
  return Number(h) % 24 // some engines emit "24" at midnight
}

// Atomically claim (job, London-day) in cron_runs (migration 043). Returns true if the job ALREADY ran
// today and this run should skip, false if this run is the first today and should proceed.
// - FORCE=1 always returns false so manual workflow_dispatch test runs always send.
// - The insert uses PostgREST "ignore-duplicates": a duplicate returns an empty array (already ran).
// - Any error returns true (skip) so a transient DB failure never causes a double-send; the healthcheck
//   / missing message surfaces the miss and it can be re-run manually with FORCE=1.
export async function alreadyRanToday(job) {
  if (process.env.FORCE === "1") return false
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return false // no DB configured: fall back to gate-only behaviour
  try {
    const res = await fetch(`${url}/rest/v1/cron_runs`, {
      method: "POST",
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        Prefer: "resolution=ignore-duplicates,return=representation",
      },
      body: JSON.stringify({ job, run_date: londonDate() }),
    })
    if (!res.ok) {
      console.error("[alreadyRanToday]", job, res.status, await res.text())
      return true // treat as already-ran: skip rather than risk a duplicate send
    }
    const rows = await res.json()
    return Array.isArray(rows) && rows.length === 0 // empty => duplicate ignored => already ran today
  } catch (err) {
    console.error("[alreadyRanToday]", job, err)
    return true
  }
}
