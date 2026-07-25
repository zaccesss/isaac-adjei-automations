// Tops up the current year's row in github_contributions_days/_years more often than the portfolio's
// own Vercel cron does. Vercel Hobby caps a cron at once a day, so the dashboard's contribution
// calendar only reflects a day's commits after the next 05:00 London sync; this fills that gap by
// dispatching the same idempotent sync several times a day. Only the current year is re-fetched -
// past years never change once they have ended, and a full historical backfill is the daily cron's
// job, not this one's. Node only, no deps.

import { guard } from "./lib/report-failure.mjs"

guard("github-contributions-sync")

const PAT = process.env.GH_PAT
const GH_OWNER = process.env.GH_OWNER || "zaccesss"
const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!PAT) {
  console.log("GH_PAT not set - skipping.")
  process.exit(0)
}

// A one-off GraphQL blip clears on the next call - retrying beats letting it page #errors for a job
// that runs every 3 hours anyway.
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

async function main() {
  const year = new Date().getFullYear()
  const from = `${year}-01-01T00:00:00Z`
  const to = `${year}-12-31T23:59:59Z`

  const res = await retry(async () => {
    const r = await fetch("https://api.github.com/graphql", {
      method: "POST",
      headers: { Authorization: `bearer ${PAT}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        query: `query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              totalCommitContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
              totalIssueContributions
              contributionCalendar {
                weeks { contributionDays { date contributionCount } }
              }
            }
          }
        }`,
        variables: { login: GH_OWNER, from, to },
      }),
    })
    if (!r.ok) throw new Error(`graphql ${r.status} ${await r.text()}`)
    return r
  })

  const json = await res.json()
  if (json.errors?.length) throw new Error(`graphql errors: ${JSON.stringify(json.errors)}`)
  const col = json.data?.user?.contributionsCollection
  if (!col) throw new Error("no contributionsCollection in response")

  // GitHub's contributionCalendar returns one entry per day across the whole requested range,
  // including days later in the year that have not happened yet - the same future-padding bug the
  // portfolio's own sync had to filter out, so this carries the identical guard rather than storing
  // placeholder rows a frequent sync would then upsert every 3 hours.
  const todayIso = new Date().toISOString().slice(0, 10)
  const days = col.contributionCalendar.weeks
    .flatMap((w) => w.contributionDays)
    .map((d) => ({ date: d.date, count: d.contributionCount }))
    .filter((d) => d.date <= todayIso)

  if (days.length) {
    const up = await fetch(`${SUPABASE_URL}/rest/v1/github_contributions_days?on_conflict=date`, {
      method: "POST",
      headers: {
        apikey: SERVICE_KEY,
        Authorization: `Bearer ${SERVICE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "resolution=merge-duplicates,return=representation",
      },
      body: JSON.stringify(days),
    })
    if (!up.ok) throw new Error(`days upsert ${up.status} ${await up.text()}`)
  }

  const total = col.contributionCalendar.weeks
    .flatMap((w) => w.contributionDays)
    .reduce((sum, d) => sum + d.contributionCount, 0)

  const yearUp = await fetch(`${SUPABASE_URL}/rest/v1/github_contributions_years?on_conflict=year`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=representation",
    },
    body: JSON.stringify([
      {
        year,
        commits: col.totalCommitContributions ?? 0,
        pull_requests: col.totalPullRequestContributions ?? 0,
        reviews: col.totalPullRequestReviewContributions ?? 0,
        issues: col.totalIssueContributions ?? 0,
        total,
        synced_at: new Date().toISOString(),
      },
    ]),
  })
  if (!yearUp.ok) throw new Error(`year upsert ${yearUp.status} ${await yearUp.text()}`)

  console.log(`Synced ${year}: ${days.length} days, ${total} contributions.`)
}

// No local .catch: a throw here becomes an unhandled rejection, which the guard above reports in full
// to #errors and then exits non-zero. A local catch would swallow it and the failure would only ever
// reach the run log.
await main()
