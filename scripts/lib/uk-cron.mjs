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
// - On a DB error it THROWS. On error I cannot tell whether today's run already happened, so the old
//   code skipped silently (exit 0) and the miss looked like a clean success. Throwing instead lets the
//   caller's guard report it to #errors and exit non-zero, so Healthchecks /fail fires. The claim did
//   not land, so a later run (or a FORCE=1 rerun) still sends exactly once - no double-send, because
//   the claim runs before any message is sent.
export async function alreadyRanToday(job) {
  if (process.env.FORCE === "1") return false
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return false // no DB configured: fall back to gate-only behaviour
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
  if (!res.ok) throw new Error(`[alreadyRanToday] ${job} claim failed: ${res.status} ${await res.text()}`)
  const rows = await res.json()
  return Array.isArray(rows) && rows.length === 0 // empty => duplicate ignored => already ran today
}

// Release today's (job, London-day) claim from cron_runs so a later run can retry. Used when a job
// claimed the day up front (to stop a double-send) but then produced nothing - e.g. every section
// failed - so the day must NOT count as done. Best-effort: a failure here is logged, never thrown,
// because the caller is already on its failure path and about to exit non-zero anyway.
export async function releaseClaim(job) {
  if (process.env.FORCE === "1") return
  const url = process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) return
  try {
    const res = await fetch(`${url}/rest/v1/cron_runs?job=eq.${encodeURIComponent(job)}&run_date=eq.${londonDate()}`, {
      method: "DELETE",
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    })
    if (!res.ok) console.error("[releaseClaim]", job, res.status, await res.text())
  } catch (err) {
    console.error("[releaseClaim]", job, err)
  }
}
