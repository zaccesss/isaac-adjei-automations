// Geocodes every distinct applications.location string not yet cached in location_geocodes
// (isaac-adjei-portfolio migration 049), so the Applications analytics map can plot real pins
// without the website ever calling a geocoder itself - it only ever reads this cache. OpenCage is
// the primary geocoder (needs OPENCAGE_API_KEY); a location it fails to resolve gets one retry via
// Nominatim (OpenStreetMap's own geocoder, free, no key) before being cached as unresolved
// (lat/lng null) so it is never retried forever. Node only, no deps.
//
// Persists in chunks as it goes (CHUNK_SIZE) rather than one upsert after the whole loop. A large
// backlog can take longer than the workflow's own 10-minute timeout; a killed run used to lose
// every result it had already fetched since nothing was saved until the very end. Confirmed live:
// this is exactly what burned OpenCage's account well past its free-tier daily limit for a week
// straight (10k-18k calls/day against a 2,500 cap) - most of those calls were thrown away by a
// killed run, so the same still-pending backlog got re-attempted from scratch on every subsequent
// hourly run. Also stops the run outright the moment OpenCage reports its quota is exhausted
// (HTTP 402) rather than continuing to burn calls against a service that is already refusing, or
// falling every remaining location through to Nominatim's 1-request-per-second fallback (which
// would itself blow the time budget on a large backlog). Untouched locations are simply left
// pending for the next run rather than cached as unresolved, since a quota exhaustion says nothing
// about whether any individual address is actually resolvable.

import { guard } from "./lib/report-failure.mjs"

guard("geocode-locations")

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const OPENCAGE_API_KEY = process.env.OPENCAGE_API_KEY

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!OPENCAGE_API_KEY) {
  console.log("OPENCAGE_API_KEY not set - skipping.")
  process.exit(0)
}

async function sbGet(path) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: { apikey: SERVICE_KEY, Authorization: `Bearer ${SERVICE_KEY}` },
  })
  if (!res.ok) throw new Error(`GET ${path} ${res.status} ${await res.text()}`)
  return res.json()
}

async function sbUpsert(table, rows, onConflict) {
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

// A dedicated error class rather than a boolean return, so the 402 case can propagate up through
// the same try/catch every other OpenCage failure already goes through without a second code path.
class OpenCageQuotaExceeded extends Error {}

async function geocodeOpenCage(location) {
  const url = `https://api.opencagedata.com/geocode/v1/json?q=${encodeURIComponent(location)}&key=${OPENCAGE_API_KEY}&limit=1&no_annotations=1`
  const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
  // OpenCage's documented quota-exceeded response is HTTP 402, distinct from a plain no-match
  // (which is still a 200 with an empty results array) or a transient error.
  if (res.status === 402) throw new OpenCageQuotaExceeded()
  if (!res.ok) return null
  const data = await res.json()
  const hit = data?.results?.[0]?.geometry
  return hit ? { lat: hit.lat, lng: hit.lng } : null
}

// Fallback only - Nominatim's usage policy caps requests at 1/sec, which this respects since it
// is only ever reached for the small remainder OpenCage could not resolve, one location at a time.
async function geocodeNominatim(location) {
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(location)}&format=json&limit=1`
  const res = await fetch(url, {
    signal: AbortSignal.timeout(8000),
    headers: { "User-Agent": "isaacadjei.me application-map geocoder (contact via isaacadjei.me)" },
  })
  if (!res.ok) return null
  const data = await res.json()
  const hit = data?.[0]
  return hit ? { lat: Number(hit.lat), lng: Number(hit.lon) } : null
}

// PostgREST caps a single select at 1000 rows. A plain unpaginated select only ever sees the first
// 1000 of a bigger table - originally found stranding applications (~12,000 rows, most scraped)
// outside that window forever. Re-found live when location_geocodes itself grew past 1000 rows: an
// unpaginated fetch of the cache started silently missing several hundred already-cached rows, so
// the script wrongly treated real, already-resolved locations as pending and started re-hitting
// OpenCage for them. Both queries in this file that can plausibly exceed 1000 rows page through
// explicitly via this one shared helper rather than assuming either table stays small.
async function fetchAllPages(pathWithoutPaging) {
  const pageSize = 1000
  let offset = 0
  const all = []
  const sep = pathWithoutPaging.includes("?") ? "&" : "?"
  for (;;) {
    const page = await sbGet(`${pathWithoutPaging}${sep}limit=${pageSize}&offset=${offset}`)
    all.push(...page)
    if (page.length < pageSize) break
    offset += pageSize
  }
  return all
}

async function main() {
  const applications = await fetchAllPages("applications?select=location&location=not.is.null")
  const distinctLocations = [...new Set(applications.map((a) => a.location).filter((l) => l && l.trim()))]
  if (!distinctLocations.length) {
    console.log("No application locations to check.")
    return
  }

  // Fetches every cached location unfiltered rather than building a PostgREST in.() filter with
  // hundreds of arbitrary strings - location text can contain commas, semicolons and parentheses
  // (e.g. "Berlin; London; Munich"), which breaks a hand-built in.() list at this scale.
  const cached = await fetchAllPages("location_geocodes?select=location")
  const cachedSet = new Set(cached.map((c) => c.location))
  const pending = distinctLocations.filter((l) => !cachedSet.has(l))

  if (!pending.length) {
    console.log("All application locations already geocoded.")
    return
  }

  const CHUNK_SIZE = 50
  let buffer = []
  let totalProcessed = 0
  let totalResolved = 0
  let quotaExceeded = false

  async function flush() {
    if (!buffer.length) return
    await sbUpsert("location_geocodes", buffer, "location")
    totalProcessed += buffer.length
    totalResolved += buffer.filter((r) => r.lat != null).length
    buffer = []
  }

  for (const location of pending) {
    let hit = null
    try {
      hit = await geocodeOpenCage(location)
    } catch (err) {
      if (err instanceof OpenCageQuotaExceeded) {
        quotaExceeded = true
        break
      }
      hit = null
    }
    if (!hit) {
      try {
        hit = await geocodeNominatim(location)
      } catch {
        hit = null
      }
      // Only reached when a Nominatim fallback attempt actually happened - stays under its 1/sec policy.
      await new Promise((r) => setTimeout(r, 1000))
    }
    buffer.push({ location, lat: hit?.lat ?? null, lng: hit?.lng ?? null, resolved_at: new Date().toISOString() })
    if (buffer.length >= CHUNK_SIZE) await flush()
  }

  await flush()

  if (quotaExceeded) {
    const remaining = pending.length - totalProcessed
    console.log(
      `OpenCage quota exceeded, stopped early. Geocoded ${totalResolved}/${totalProcessed} before stopping, ` +
      `${remaining} location${remaining === 1 ? "" : "s"} left pending for a future run once quota resets.`,
    )
    return
  }

  console.log(`Geocoded ${totalResolved}/${totalProcessed} new locations (${totalProcessed - totalResolved} unresolved, cached to avoid retrying).`)
}

await main()
