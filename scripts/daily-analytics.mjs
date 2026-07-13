// Posts a daily analytics summary to each dashboard analytics channel (Applications, Posts, Fitness,
// Music) for the day that just ended. Runs just after midnight UK, once the coding recap is out, so the
// numbers are waiting first thing. Resilient to GitHub Actions cron being delayed or
// dropped: the workflow fires from a frequent morning schedule, this proceeds only once the London hour has
// reached the target, and alreadyRanToday claims (job, UK-day) so it sends exactly once whenever a run
// finally lands. Node only, no deps. Each channel is optional - a page is skipped if its webhook is unset.
import { londonDate, londonHour, alreadyRanToday, releaseClaim } from "./lib/uk-cron.mjs"
import { guard } from "./lib/report-failure.mjs"

guard("daily-analytics")

const SUPABASE_URL = process.env.SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const TARGET_HOUR = 1

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.log("Missing Supabase env - skipping.")
  process.exit(0)
}

async function get(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
  })
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`)
  return res.json()
}

// Page past PostgREST's 1000-row cap. The caller passes a path already carrying its filters and a
// stable order; I append offset/limit and read until a short page. Needed for applications, where the
// scraped rows (thousands of them) otherwise fill the first 1000 and evict the real ones.
async function getAll(pathBase) {
  const rows = []
  for (let offset = 0; ; offset += 1000) {
    const page = await get(`${pathBase}&offset=${offset}&limit=1000`)
    rows.push(...page)
    if (page.length < 1000) break
  }
  return rows
}

async function send(webhook, title, lines) {
  if (!webhook) return false
  const res = await fetch(webhook, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      embeds: [{ title, description: lines.filter(Boolean).join("\n"), color: 0x6366f1, footer: { text: "isaacadjei.me/dashboard" }, timestamp: new Date().toISOString() }],
    }),
  })
  if (!res.ok) console.error(`Discord "${title}": ${res.status} ${await res.text()}`)
  return res.ok
}

// Gate + claim (skipped by FORCE=1 for manual test runs).
if (process.env.FORCE !== "1") {
  if (londonHour() < TARGET_HOUR) {
    console.log(`Too early (${londonHour()} < ${TARGET_HOUR} UK) - skipping.`)
    process.exit(0)
  }
  if (await alreadyRanToday("daily-analytics")) {
    console.log("Already ran today - skipping.")
    process.exit(0)
  }
}

const yesterday = londonDate(new Date(Date.now() - 24 * 60 * 60 * 1000))
const dayStart = `${yesterday}T00:00:00`
const dayEnd = `${yesterday}T23:59:59`
const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10)
const label = new Date(`${yesterday}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/London" })

let sent = 0

// ── Applications ──
try {
  // Exclude the scraped rows server-side (they are not real applications and there are thousands) and
  // page the rest, so the counts reflect every genuine application rather than a truncated first 1000.
  const apps = await getAll(`applications?select=status,applied_date&status=neq.scraped&order=id`)
  const skip = new Set(["Not Applied", "Not Interested", "scraped"])
  const interview = new Set(["Interview", "Assessment Centre", "Video Interview", "Face-to-face Interview", "Telephone Interview"])
  const live = apps.filter((a) => !skip.has(a.status))
  const appliedYesterday = apps.filter((a) => a.applied_date === yesterday).length
  const interviews = live.filter((a) => interview.has(a.status)).length
  const offers = live.filter((a) => a.status === "Offer Received").length
  if (await send(process.env.DISCORD_WEBHOOK_APPLICATIONS, `📊 Applications - ${label}`, [
    `Applied yesterday: **${appliedYesterday}**`,
    `Live pipeline: **${live.length}** · Interviewing: **${interviews}** · Offers: **${offers}**`,
  ])) sent++
} catch (e) {
  console.error("applications:", e.message)
}

// ── Posts (scroll-depth opens) ──
try {
  const opens = await get(`blog_read_events?select=slug&depth=eq.25&created_at=gte.${dayStart}&created_at=lte.${dayEnd}&limit=5000`)
  const bySlug = {}
  for (const o of opens) bySlug[o.slug] = (bySlug[o.slug] || 0) + 1
  const top = Object.entries(bySlug).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([s, n]) => `${s} (${n})`).join(", ")
  if (await send(process.env.DISCORD_WEBHOOK_POSTS, `📊 Posts - ${label}`, [
    `Opens yesterday: **${opens.length}**`,
    top ? `Top: ${top}` : "",
  ])) sent++
} catch (e) {
  console.error("posts:", e.message)
}

// ── Fitness (last 7 days from Strava) ──
try {
  const acts = await get(`strava_activities?select=distance_m,moving_time_s&start_date=gte.${weekAgo}&limit=1000`)
  const km = (acts.reduce((a, r) => a + (r.distance_m || 0), 0) / 1000).toFixed(1)
  const hours = (acts.reduce((a, r) => a + (r.moving_time_s || 0), 0) / 3600).toFixed(1)
  if (await send(process.env.DISCORD_WEBHOOK_FITNESS, `📊 Fitness - last 7 days`, [
    `Workouts: **${acts.length}** · Distance: **${km}km** · Moving: **${hours}h**`,
  ])) sent++
} catch (e) {
  console.error("fitness:", e.message)
}

// ── Music (yesterday's scrobbles from the collector) ──
try {
  const plays = await get(`listening_history?select=track_name,artist_name&played_at=gte.${dayStart}&played_at=lte.${dayEnd}&limit=2000`)
  const byTrack = {}
  for (const p of plays) {
    const k = `${p.track_name} - ${p.artist_name}`
    byTrack[k] = (byTrack[k] || 0) + 1
  }
  const top = Object.entries(byTrack).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t, n]) => `${t} (${n})`).join(", ")
  if (await send(process.env.DISCORD_WEBHOOK_MUSIC, `📊 Music - ${label}`, [
    `Plays yesterday: **${plays.length}**`,
    top ? `Top: ${top}` : "",
  ])) sent++
} catch (e) {
  console.error("music:", e.message)
}

// If every section failed, the day produced nothing. alreadyRanToday already claimed it up front to
// stop a double-post, so release that claim for a later run to retry, and exit non-zero so Healthchecks
// /fail fires instead of this reading as a clean, complete run.
if (sent === 0) {
  await releaseClaim("daily-analytics")
  console.error(`Daily analytics for ${yesterday}: every section failed, nothing posted. Released the claim to retry.`)
  process.exit(1)
}

console.log(`Daily analytics done for ${yesterday}. ${sent} channel(s) posted.`)
