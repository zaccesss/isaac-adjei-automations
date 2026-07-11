// Shared failure reporter for the Node jobs. When a job crashes, I post the full error - stack trace
// plus a link to the exact Actions run - to the #errors channel, then exit non-zero so the workflow
// still fails and the Healthchecks /fail ping fires. Best-effort: a webhook problem never hides the
// original error, which always goes to the run log too. Wire it in with two lines at the top of a
// script: import guard, then guard("<slug>").

function runUrl() {
  const s = process.env.GITHUB_SERVER_URL
  const r = process.env.GITHUB_REPOSITORY
  const id = process.env.GITHUB_RUN_ID
  return s && r && id ? `${s}/${r}/actions/runs/${id}` : ""
}

export async function postFailure(job, err) {
  const detail = String(err && (err.stack || err.message) ? err.stack || err.message : err)
  const trace = detail.length > 1500 ? `${detail.slice(0, 1500)}\n... truncated, full trace in the run log` : detail
  const url = runUrl()
  const content = [`\u{1F534} **${job}** failed`, url ? `↳ ${url}` : "", "```", trace, "```"]
    .filter(Boolean)
    .join("\n")
  const webhook = process.env.DISCORD_WEBHOOK_ERRORS || ""
  if (!webhook) return
  try {
    await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    })
  } catch (e) {
    console.error("could not post to #errors:", e?.message || e)
  }
}

// Install crash handlers so any thrown or rejected error anywhere in the job is reported in full then
// re-exits non-zero. Covers both top-level-await scripts and scripts wrapped in a main().
export function guard(job) {
  const handle = async (err) => {
    console.error(err)
    await postFailure(job, err)
    process.exit(1)
  }
  process.on("unhandledRejection", handle)
  process.on("uncaughtException", handle)
}
