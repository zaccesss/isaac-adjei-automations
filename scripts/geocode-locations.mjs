// Geocodes every distinct applications.location string not yet cached in location_geocodes
// (isaac-adjei-portfolio migration 049), so the Applications analytics map can plot real pins
// without the website ever calling a geocoder itself - it only ever reads this cache. OpenCage is
// the primary geocoder (needs OPENCAGE_API_KEY); a location it fails to resolve gets one retry via
// Nominatim (OpenStreetMap's own geocoder, free, no key) before being cached as unresolved
// (lat/lng null) so it is never retried forever. Node only, no deps.

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

async function geocodeOpenCage(location) {
  const url = `https://api.opencagedata.com/geocode/v1/json?q=${encodeURIComponent(location)}&key=${OPENCAGE_API_KEY}&limit=1&no_annotations=1`
  const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
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

async function main() {
  const applications = await sbGet("applications?select=location&location=not.is.null")
  const distinctLocations = [...new Set(applications.map((a) => a.location).filter((l) => l && l.trim()))]
  if (!distinctLocations.length) {
    console.log("No application locations to check.")
    return
  }

  const cached = await sbGet(
    `location_geocodes?select=location&location=in.(${distinctLocations.map((l) => `"${l.replace(/"/g, '""')}"`).join(",")})`,
  )
  const cachedSet = new Set(cached.map((c) => c.location))
  const pending = distinctLocations.filter((l) => !cachedSet.has(l))

  if (!pending.length) {
    console.log("All application locations already geocoded.")
    return
  }

  const rows = []
  for (const location of pending) {
    let hit = null
    try {
      hit = await geocodeOpenCage(location)
    } catch {
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
    rows.push({ location, lat: hit?.lat ?? null, lng: hit?.lng ?? null, resolved_at: new Date().toISOString() })
  }

  await sbUpsert("location_geocodes", rows, "location")
  const resolved = rows.filter((r) => r.lat != null).length
  console.log(`Geocoded ${resolved}/${rows.length} new locations (${rows.length - resolved} unresolved, cached to avoid retrying).`)
}

await main()
