// Records my Spotify plays into the listening_history table so the dashboard and lab pages can show
// real listening analytics - play counts, active hours, streaks - that the Spotify API alone cannot
// give (it only returns top-N and the last 50 plays). I fetch the recently-played endpoint and upsert
// each play, deduped by played_at. Node only, no deps.

const CID = process.env.SPOTIFY_CLIENT_ID
const SEC = process.env.SPOTIFY_CLIENT_SECRET
const RT = process.env.SPOTIFY_REFRESH_TOKEN
const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
  process.exit(1)
}
if (!CID || !SEC || !RT) {
  console.log("Spotify credentials not set (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN) - skipping.")
  process.exit(0)
}

async function accessToken() {
  const res = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${Buffer.from(`${CID}:${SEC}`).toString("base64")}`,
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: RT }),
  })
  if (!res.ok) throw new Error(`token ${res.status} ${await res.text()}`)
  return (await res.json()).access_token
}

async function main() {
  const token = await accessToken()
  const res = await fetch("https://api.spotify.com/v1/me/player/recently-played?limit=50", {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`recently-played ${res.status} ${await res.text()}`)
  const items = (await res.json()).items || []
  if (!items.length) {
    console.log("No recent plays to record.")
    return
  }

  const rows = items.map((it) => {
    const t = it.track || {}
    return {
      played_at: it.played_at,
      track_id: t.id || null,
      track_name: t.name || "Unknown",
      artist_name: (t.artists || []).map((a) => a.name).join(", ") || "Unknown",
      album_name: t.album?.name || null,
      album_art: t.album?.images?.[1]?.url || t.album?.images?.[0]?.url || null,
      duration_ms: t.duration_ms || null,
      url: t.external_urls?.spotify || null,
    }
  })

  // Upsert deduped by played_at - plays I already stored are ignored, so re-runs are safe.
  const up = await fetch(`${SUPABASE_URL}/rest/v1/listening_history?on_conflict=played_at`, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=ignore-duplicates,return=representation",
    },
    body: JSON.stringify(rows),
  })
  if (!up.ok) throw new Error(`upsert ${up.status} ${await up.text()}`)
  const inserted = await up.json()
  console.log(`Fetched ${rows.length} recent plays, stored ${inserted.length} new.`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
