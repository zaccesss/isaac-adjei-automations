"""The ATS company lists, the priority companies and the student department names."""


# I apply a looser filter for priority companies because a Software Engineer
# role at Google is still worth knowing about even if "intern" is absent.
PRIORITY_COMPANIES = {
    "google", "amazon", "apple", "microsoft", "meta", "netflix", "nvidia",
    "arm", "rolls-royce", "rolls royce", "sky", "skyscanner", "spotify",
    "github", "playstation", "sony", "bbc", "bt", "deloitte", "pwc",
    "goldman sachs", "morgan stanley", "jpmorgan", "jp morgan", "bloomberg",
    "deepmind", "anthropic", "openai", "palantir", "cloudflare",
    "salesforce", "oracle", "sap", "ibm", "intel", "amd", "qualcomm",
    "siemens", "bosch", "jlr", "jaguar land rover", "aston martin",
    "dyson", "mclaren", "national grid", "nhs", "gchq", "hmrc",
    "civil service", "dstl", "qinetiq", "stripe", "figma", "notion",
    "jane street", "citadel", "two sigma", "jump trading", "optiver",
    "de shaw", "d. e. shaw", "susquehanna", "sig", "flow traders",
    "virtu", "imc trading", "imc", "akuna", "hudson river trading",
    "databricks", "snowflake", "hashicorp", "grafana", "mongodb",
    "elastic", "confluent", "datadog", "fastly", "akamai", "digitalocean",
    "canonical", "red hat", "jetbrains", "atlassian", "shopify",
    "block", "square", "brex", "revolut", "monzo", "wise", "starling",
    "checkout.com", "klarna", "adyen", "waymo", "cruise", "zoox",
    "aurora", "mobileye", "hugging face", "cohere", "mistral",
    "boeing", "airbus", "bae systems", "leonardo", "thales",
    "ericsson", "nokia", "mediatek", "broadcom", "bytedance", "tiktok",
    "samsara", "anduril", "coreweave", "scale ai", "perplexity",
    "cursor", "linear", "vercel", "g-research", "g research",
    "worldquant", "man group", "marshall wace", "winton",
    "barclays", "hsbc", "natwest", "lloyds", "standard chartered",
    "accenture", "capgemini", "thoughtworks",
    # Cloud & security companies I specifically want to track
    "crowdstrike", "palo alto networks", "paloaltonetworks", "zscaler",
    "okta", "auth0", "snyk", "wiz", "lacework", "orca security",
    "gitlab", "jfrog", "harness", "circleci", "buildkite",
    "new relic", "dynatrace", "sumologic", "sumo logic", "splunk",
    "sendgrid", "vonage", "bandwidth",
    "digitalocean", "linode", "vultr", "hetzner",
    "nginx", "kong", "istio", "envoy",
    # More quant/finance shops
    "jane street", "hudson river trading", "hrt", "xtw markets", "xtx",
    "tower research", "virtu", "drw", "squarepoint",
    "renaissance technologies", "two sigma", "d.e. shaw",
    # Hardware and deep tech
    "graphcore", "cerebras", "groq", "tenstorrent", "mythic",
    "riverlane", "quantinuum", "phasecraft", "pasqal",
    "oxford nanopore", "illumina", "10x genomics",
    "wayve", "five ai", "oxbotica", "oxa",
    # More UK tech companies
    "revolut", "checkout.com", "weaveworks", "thought machine",
    "onfido", "improbable", "babylon health", "benevolentai",
    "darktrace", "sophos", "micro focus", "aveva",
}

# I also check Greenhouse department names because some companies tag their
# student pipeline departments rather than including "intern" in every title.
STUDENT_DEPTS = {
    "early talent", "university", "intern", "internship", "student",
    "campus", "early career", "new grad", "university recruiting",
}


# ─── COMPANY LISTS ──────────────────────────────────────────────────────────

# I group companies by ATS vendor so it is easy to add new ones in the right
# section. Each tuple is (ats_slug, display_name).

# (greenhouse_slug, display_name)
# I keep only slugs confirmed to return HTTP 200 in recent runs.
# Companies that migrated away from Greenhouse return 404 for every request
# and are not guessed - wrong slugs never match their new ATS.
GREENHOUSE_COMPANIES = [
    # API companies
    ("cloudflare",    "Cloudflare"),
    ("stripe",        "Stripe"),
    ("figma",         "Figma"),
    ("anthropic",     "Anthropic"),
    ("databricks",    "Databricks"),
    ("coinbase",      "Coinbase"),
    ("samsara",       "Samsara"),
    ("coreweave",     "CoreWeave"),
    ("imc",           "IMC Trading"),
    ("janestreet",    "Jane Street"),
    ("datadog",       "Datadog"),
    ("gitlab",        "GitLab"),
    ("twilio",        "Twilio"),
    ("pagerduty",     "PagerDuty"),
    ("adyen",         "Adyen"),
    ("dropbox",       "Dropbox"),
    ("fastly",        "Fastly"),
    ("asana",         "Asana"),
    ("intercom",      "Intercom"),
    ("amplitude",     "Amplitude"),
    ("mixpanel",      "Mixpanel"),
    ("postman",       "Postman"),
    ("robinhood",     "Robinhood"),
    ("starburst",     "Starburst"),
    ("collibra",      "Collibra"),
    ("cockroachlabs", "CockroachDB"),
    ("atlassian",     "Atlassian"),
    # Confirmed working slugs added after live API validation
    ("mongodb",       "MongoDB"),
    ("elastic",       "Elastic"),
    ("canonical",     "Canonical"),
    ("jetbrains",     "JetBrains"),
    ("airbnb",        "Airbnb"),
    ("reddit",        "Reddit"),
    ("lyft",          "Lyft"),
    ("brex",          "Brex"),
    ("okta",          "Okta"),
    ("newrelic",      "New Relic"),
    ("jfrog",         "JFrog"),
    ("scaleai",       "Scale AI"),
    ("worldquant",    "WorldQuant"),
    ("graphcore",     "Graphcore"),
    ("monzo",         "Monzo"),
    ("airtable",      "Airtable"),
    ("lattice",       "Lattice"),
    ("carta",         "Carta"),
    ("skyscanner",    "Skyscanner"),
    ("winton",        "Winton"),
    ("spacex",        "SpaceX"),
]

# Lever slugs confirmed to return HTTP 200 with real listings.
LEVER_COMPANIES = [
    ("palantir",     "Palantir"),
    ("wealthsimple", "Wealthsimple"),
    ("cloudinary",   "Cloudinary"),
    ("spotify",      "Spotify"),
]

# (ashby_slug, display_name) - confirmed against live API.
ASHBY_COMPANIES = [
    ("linear",          "Linear"),
    ("perplexityai",    "Perplexity AI"),
    ("cursor",          "Cursor"),
    ("vercel",          "Vercel"),
    ("railway",         "Railway"),
    ("loom",            "Loom"),
    ("iter",            "Iter"),
    ("mistralai",       "Mistral AI"),
    ("huggingface",     "Hugging Face"),
    ("supabase",        "Supabase"),
    ("neon",            "Neon"),
    ("turso",           "Turso"),
    ("planetscale",     "PlanetScale"),
    ("openai",          "OpenAI"),
    ("deepmind",        "Google DeepMind"),
    ("waymo",           "Waymo"),
    ("anyscale",        "Anyscale"),
    # Expanded - all confirmed against live API (June 2026)
    ("notion",          "Notion"),
    ("replit",          "Replit"),
    ("benchling",       "Benchling"),
    ("snowflake",       "Snowflake"),
    ("confluent",       "Confluent"),
    ("plaid",           "Plaid"),
    ("sentry",          "Sentry"),
    ("posthog",         "PostHog"),
    ("resend",          "Resend"),
    ("deliveroo",       "Deliveroo"),
    ("redis",           "Redis"),
    ("thought-machine", "Thought Machine"),
    ("cohere",          "Cohere"),
    ("ultra",           "Ultra"),
    # Wayve is also on Greenhouse (118 jobs) but Ashby has description/dates.
    ("wayve",           "Wayve"),
]

# I use SmartRecruiters for large UK employers that are not on Greenhouse or
# Lever - mostly consulting and telco companies that standardised on it.
SMARTRECRUITERS_COMPANIES = [
    ("KPMG",           "KPMG"),
    ("Vodafone",       "Vodafone"),
    ("CapgeminiGroup", "Capgemini"),
    ("Accenture",      "Accenture"),
    ("CGI",            "CGI"),
    ("Fujitsu",        "Fujitsu"),
    ("Atos",           "Atos"),
    ("DXC",            "DXC Technology"),
    ("BT",             "BT"),
    ("Virgin",         "Virgin Media O2"),
    ("Siemens",        "Siemens"),
    ("IBM",            "IBM"),
    ("NatWest",        "NatWest"),
    ("Barclays",       "Barclays"),
    ("HSBC",           "HSBC"),
    ("BritishAirways", "British Airways"),
    ("RollsRoyce",     "Rolls-Royce"),
    ("BAEsystems",     "BAE Systems"),
    ("Airbus",         "Airbus"),
    ("AstraZeneca",    "AstraZeneca"),
    ("GlaxoSmithKline","GSK"),
    ("BPGlobal",       "BP"),
    ("Shell",          "Shell"),
    ("Deloitte",       "Deloitte"),
    ("PwC",            "PwC"),
    ("EY",             "EY"),
]
