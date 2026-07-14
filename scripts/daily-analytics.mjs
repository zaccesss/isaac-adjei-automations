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
const label = new Date(`${yesterday}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/London" })

// Formatting shared by the sections below.
const fmtDur = (s) => {
  const m = Math.round(s / 60)
  return m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m` : `${m}m`
}
const fmtDay = (d) => new Date(`${d}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Europe/London" })
const spaceCamel = (s) => s.replace(/([a-z])([A-Z])/g, "$1 $2")

let sent = 0

// ── Applications ──
try {
  // Exclude the scraped rows server-side (they are not real applications and there are thousands) and
  // page the rest, so the counts reflect every genuine application rather than a truncated first 1000.
  const apps = await getAll(`applications?select=status,applied_date,company,role,category,location,work_mode,deadline&status=neq.scraped&order=id`)
  const skip = new Set(["Not Applied", "Not Interested", "scraped"])
  const interview = new Set(["Interview", "Assessment Centre", "Video Interview", "Face-to-face Interview", "Telephone Interview"])
  const live = apps.filter((a) => !skip.has(a.status))
  const appliedYesterday = apps.filter((a) => a.applied_date === yesterday)
  const interviews = live.filter((a) => interview.has(a.status)).length
  const offers = live.filter((a) => a.status === "Offer Received").length
  const roleLine = (a) => [[a.company, a.role].filter(Boolean).join(" - "), a.category, a.work_mode, a.location].filter(Boolean).join(" · ")
  const appliedLines = appliedYesterday.slice(0, 5).map((a) => `• ${roleLine(a)}`)
  if (appliedYesterday.length > 5) appliedLines.push(`plus ${appliedYesterday.length - 5} more`)
  // Deadlines due in the coming week, including openings still marked Not Applied - those are the
  // ones a warning can actually save.
  const today = londonDate(new Date())
  const weekOut = londonDate(new Date(Date.now() + 7 * 86400000))
  const dueLines = apps
    .filter((a) => a.status !== "Not Interested" && a.deadline && a.deadline >= today && a.deadline <= weekOut)
    .sort((a, b) => a.deadline.localeCompare(b.deadline))
    .slice(0, 5)
    .map((a) => `⏳ ${[a.company, a.role].filter(Boolean).join(" - ")} closes ${fmtDay(a.deadline)}${a.status === "Not Applied" ? " (not applied yet)" : ""}`)
  const byCat = {}
  for (const a of live) byCat[a.category || "Uncategorised"] = (byCat[a.category || "Uncategorised"] || 0) + 1
  const catLine = Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([c, n]) => `${c} ${n}`).join(" · ")
  if (await send(process.env.DISCORD_WEBHOOK_APPLICATIONS, `📊 Applications - ${label}`, [
    `Applied yesterday: **${appliedYesterday.length}**`,
    ...appliedLines,
    `Live pipeline: **${live.length}** · Interviewing: **${interviews}** · Offers: **${offers}**`,
    catLine ? `By category: ${catLine}` : "",
    ...dueLines,
  ])) sent++
} catch (e) {
  console.error("applications:", e.message)
}

// ── Posts (scroll-depth opens + finished reads) ──
try {
  const events = await get(`blog_read_events?select=slug,post_type,depth&depth=in.(25,100)&created_at=gte.${dayStart}&created_at=lte.${dayEnd}&limit=5000`)
  const opens = events.filter((e) => e.depth === 25)
  const finished = events.filter((e) => e.depth === 100)
  const byType = {}
  for (const o of opens) byType[o.post_type || "blog"] = (byType[o.post_type || "blog"] || 0) + 1
  const typeBits = Object.entries(byType).sort((a, b) => b[1] - a[1]).map(([t, n]) => `${t} ${n}`).join(" · ")
  const bySlug = {}
  for (const o of opens) bySlug[o.slug] = (bySlug[o.slug] || 0) + 1
  const finishedBySlug = {}
  for (const f of finished) finishedBySlug[f.slug] = (finishedBySlug[f.slug] || 0) + 1
  const top = Object.entries(bySlug)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([s, n]) => `${s} (${n}${finishedBySlug[s] ? ` · ${finishedBySlug[s]} finished` : ""})`)
    .join(", ")
  if (await send(process.env.DISCORD_WEBHOOK_POSTS, `📊 Posts - ${label}`, [
    `Opens yesterday: **${opens.length}**${typeBits ? ` (${typeBits})` : ""} · Finished reads: **${finished.length}**`,
    top ? `Top: ${top}` : "",
  ])) sent++
} catch (e) {
  console.error("posts:", e.message)
}

// ── Fitness (yesterday's Strava activities) ──
try {
  const acts = await get(
    `strava_activities?select=sport_type,distance_m,moving_time_s,average_heartrate,max_heartrate,calories,total_elevation_gain_m&start_date=gte.${dayStart}&start_date=lte.${dayEnd}&order=start_date&limit=100`,
  )
  const actLines = acts.map((a) => {
    const bits = [spaceCamel(a.sport_type || "Workout")]
    if (a.distance_m) bits.push(`${(a.distance_m / 1000).toFixed(1)}km`)
    if (a.moving_time_s) bits.push(fmtDur(a.moving_time_s))
    if (a.average_heartrate) bits.push(`❤️ ${Math.round(a.average_heartrate)} avg${a.max_heartrate ? ` / ${Math.round(a.max_heartrate)} max` : ""}`)
    if (a.calories) bits.push(`${Math.round(a.calories)} kcal`)
    if (a.total_elevation_gain_m) bits.push(`↗ ${Math.round(a.total_elevation_gain_m)}m`)
    return `• ${bits.join(" · ")}`
  })
  const km = acts.reduce((t, a) => t + (a.distance_m || 0), 0) / 1000
  const moving = acts.reduce((t, a) => t + (a.moving_time_s || 0), 0)
  const kcal = acts.reduce((t, a) => t + (a.calories || 0), 0)
  const climb = acts.reduce((t, a) => t + (a.total_elevation_gain_m || 0), 0)
  const summary = acts.length
    ? `Workouts: **${acts.length}** · Distance: **${km.toFixed(1)}km** · Moving: **${fmtDur(moving)}**${kcal ? ` · Burned: **${Math.round(kcal)} kcal**` : ""}${climb ? ` · Climb: **${Math.round(climb)}m**` : ""}`
    : "Rest day - nothing logged."
  if (await send(process.env.DISCORD_WEBHOOK_FITNESS, `📊 Fitness - ${label}`, [summary, ...actLines])) sent++
} catch (e) {
  console.error("fitness:", e.message)
}

// ── Music (yesterday's scrobbles from the collector) ──
try {
  const plays = await get(`listening_history?select=track_name,artist_name,album_name,duration_ms&played_at=gte.${dayStart}&played_at=lte.${dayEnd}&limit=2000`)
  const listenedMs = plays.reduce((t, p) => t + (p.duration_ms || 0), 0)
  const top = (key, n) => {
    const counts = {}
    for (const p of plays) {
      const k = key(p)
      if (k) counts[k] = (counts[k] || 0) + 1
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, n)
  }
  const tracks = top((p) => `${p.track_name} - ${p.artist_name}`, 3).map(([t, n]) => `${t} (${n})`).join(", ")
  const artists = top((p) => p.artist_name, 3).map(([a, n]) => `${a} (${n})`).join(", ")
  const album = top((p) => p.album_name, 1).map(([a, n]) => `${a} (${n})`).join(", ")
  if (await send(process.env.DISCORD_WEBHOOK_MUSIC, `📊 Music - ${label}`, [
    `Plays yesterday: **${plays.length}**${listenedMs ? ` · Listening time: **${fmtDur(Math.round(listenedMs / 1000))}**` : ""}`,
    tracks ? `Top tracks: ${tracks}` : "",
    artists ? `Top artists: ${artists}` : "",
    album ? `Top album: ${album}` : "",
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
