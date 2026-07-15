# I scrape tech internships and placements from 20+ sources and upsert them into Supabase so my application tracker stays fresh without manual searching.
"""Job scraper package - runs daily via GitHub Actions as python -m scraper (two off-peak
tries; the upsert de-duplicates).

Sources:
  - The Trackr (Playwright - JS rendered, best UK internship aggregator)
  - Google Careers     (Playwright - React SPA, no public REST API)
  - Meta Careers       (Playwright - React SPA, no public REST API)
  - ARM Careers        (Playwright - Workday with proprietary session auth)
  - Goldman Sachs      (Playwright - higher.gs.com React portal)
  - JPMorgan Careers   (Playwright - React SPA, Workday with proprietary auth)
  - Greenhouse JSON API  (50+ companies)
  - Lever JSON API       (5+ companies)
  - Ashby REST API       (30+ companies)
  - Amazon Jobs JSON API (custom scraper)
  - Workday CXS API    (NVIDIA, Intel, Morgan Stanley)
  - SmartRecruiters    (JSON API)
  - Apple, Microsoft   (custom JSON APIs)
  - Reed, Adzuna, Jooble, Remotive, Arbeitnow, Jobicy (job board APIs)
  - Gradcracker, RateMyPlacement, TargetJobs, BrightNetwork (BeautifulSoup)

Only student-facing roles are saved: internships, placements, spring/insight
weeks, graduate schemes, apprenticeships. Full-time permanent roles are
skipped unless they come from a priority company and contain a keyword.

Field enrichment: cv_required defaults True for all scraped roles;
sponsors_visa and cover_letter_required are detected from job descriptions
where the ATS returns them (Greenhouse content field, Ashby descriptionPlain).
Opening dates and deadlines are populated where the ATS exposes them.

Deduplicates by URL when present, falls back to company+role.
"""
