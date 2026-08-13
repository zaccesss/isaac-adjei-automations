// Pings Healthchecks' Portfolio Website Health project every 15 minutes after confirming
// isaacadjei.me is actually reachable from the outside (a real HTTP round trip to its own /api/health
// route). No other check in that project watches the site itself - every other one watches a single
// job's own last run. Node only, no deps.

import { guard } from "./lib/report-failure.mjs"

guard("portfolio-site-up")

const PORTFOLIO_URL = process.env.PORTFOLIO_URL || "https://isaacadjei.me"
const PING_URL = process.env.HEALTHCHECKS_PORTFOLIO_SITE_PING_URL

if (!PING_URL) {
  console.log("HEALTHCHECKS_PORTFOLIO_SITE_PING_URL not set - skipping.")
  process.exit(0)
}

async function main() {
  let ok = false
  try {
    const res = await fetch(`${PORTFOLIO_URL}/api/health`, { signal: AbortSignal.timeout(8000) })
    ok = res.ok
  } catch {
    ok = false
  }

  const res = await fetch(`${PING_URL}${ok ? "" : "/fail"}`, { method: "POST", signal: AbortSignal.timeout(4000) })
  if (!res.ok) throw new Error(`Healthchecks ping ${res.status} ${await res.text()}`)

  console.log(ok ? "Site up, pinged success." : "Site unreachable, pinged fail.")
}

await main()
