# I scrape tech internships and placements from 20+ sources and upsert them into Supabase so my application tracker stays fresh without manual searching.
"""Job scraper package - runs daily via GitHub Actions as python -m scraper (two off-peak
tries; the upsert de-duplicates).

Sources (api-mode run in the fast job, browser-mode in the Playwright/Camoufox job):
  - The Trackr         (api.the-trackr.com programmes JSON, all UK Tech tabs)
  - RateMyPlacement    (embedded search JSON, placements/internships/insights)
  - Greenhouse JSON API  (50+ companies)
  - Lever JSON API       (companies list)
  - Ashby REST API       (companies list)
  - SmartRecruiters      (JSON API, live tenants)
  - Eightfold            (public /api/apply jobs, e.g. STMicroelectronics)
  - Oracle Recruiting    (recruitingCEJobRequisitions REST, JPMorgan + Texas Instruments)
  - Amazon, Apple, Microsoft (custom JSON APIs)
  - Workday CXS API      (NVIDIA, Intel, Morgan Stanley, Analog Devices, Micron, NXP, Marvell)
  - Reed, Adzuna, Jooble, Remotive, Arbeitnow, Jobicy (job board APIs)
  - Gradcracker, Bright Network, Milkround (curl_cffi HTML, Scrapling Camoufox
    fallback that solves the Cloudflare challenge from a data-centre IP)
  - Goldman Sachs        (Scrapling Camoufox render of higher.gs.com)
  - Company career sites (Playwright - ARM via Radancy JSON; Google/Meta/Goldman/
    JPMorgan legacy passes now superseded by the sources above)

Only student-facing roles are saved: internships, placements, spring/insight
weeks, graduate schemes, apprenticeships. Full-time permanent roles are
skipped unless they come from a priority company and contain a keyword.

Field enrichment: cv_required defaults True for all scraped roles;
sponsors_visa and cover_letter_required are detected from job descriptions
where the ATS returns them (Greenhouse content field, Ashby descriptionPlain).
Opening dates and deadlines are populated where the ATS exposes them.

Deduplicates by URL when present, falls back to company+role.
"""
