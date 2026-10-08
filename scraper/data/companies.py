"""The ATS company lists, the priority companies and the student department names."""


# apply a looser filter for priority companies because a Software Engineer
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
    # cloud & security companies tracked specifically
    "crowdstrike", "palo alto networks", "paloaltonetworks", "zscaler",
    "okta", "auth0", "snyk", "wiz", "lacework", "orca security",
    "gitlab", "jfrog", "harness", "circleci", "buildkite",
    "new relic", "dynatrace", "sumologic", "sumo logic", "splunk",
    "sendgrid", "vonage", "bandwidth",
    "digitalocean", "linode", "vultr", "hetzner",
    "nginx", "kong", "istio", "envoy",
    # more quant/finance shops
    "jane street", "hudson river trading", "hrt", "xtw markets", "xtx",
    "tower research", "virtu", "drw", "squarepoint",
    "renaissance technologies", "two sigma", "d.e. shaw",
    # hardware and deep tech
    "graphcore", "cerebras", "groq", "tenstorrent", "mythic",
    "riverlane", "quantinuum", "phasecraft", "pasqal",
    "oxford nanopore", "illumina", "10x genomics",
    "wayve", "five ai", "oxbotica", "oxa",
    "axelera", "psiquantum", "lightmatter",
    # more UK tech companies
    "revolut", "checkout.com", "weaveworks", "thought machine",
    "onfido", "improbable", "babylon health", "benevolentai",
    "darktrace", "sophos", "micro focus", "aveva",
    # embedded and semiconductor companies - the search covers embedded and hardware
    # placements, so these get the same looser filter as the software giants.
    "imagination technologies", "nxp", "stmicroelectronics", "st microelectronics",
    "infineon", "renesas", "texas instruments", "analog devices", "micron",
    "western digital", "nordic semiconductor", "raspberry pi", "silicon labs",
    "microchip technology", "marvell", "cirrus logic", "lattice semiconductor",
    "renishaw", "cambridge consultants", "ttp", "oxford instruments",
    "edwards vacuum", "mbda", "babcock", "ocado", "helsing", "nothing technology",
}

# also check Greenhouse department names because some companies tag their
# student pipeline departments rather than including "intern" in every title.
STUDENT_DEPTS = {
    "early talent", "university", "intern", "internship", "student",
    "campus", "early career", "new grad", "university recruiting",
    # placement-year pipelines get their own department names at UK employers.
    "placement", "industrial placement", "year in industry",
}


# ─── COMPANY LISTS ──────────────────────────────────────────────────────────

# group companies by ATS vendor so it is easy to add new ones in the right
# section. Each tuple is (ats_slug, display_name).

# (greenhouse_slug, display_name)
# keep only slugs confirmed to return HTTP 200 in recent runs.
# companies that migrated away from Greenhouse return 404 for every request
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
    # atlassian removed July 2026: migrated off Greenhouse, the slug 404s.
    # confirmed working slugs added after live API validation
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
    # embedded, hardware and UK deep tech - confirmed live July 2026. These matter
    # as much as the software names: the search covers embedded and hardware placements.
    ("tenstorrent",        "Tenstorrent"),
    ("riverlane",          "Riverlane"),
    ("nothing",            "Nothing"),
    ("helsing",            "Helsing"),
    ("ocadogroup",         "Ocado Group"),
    ("andurilindustries",  "Anduril"),
    # silicon photonics, quantum and robotics - each verified live July 2026
    # (job counts probed before adding). Their software roles come through too,
    # not only the hardware ones.
    ("lightmatter",        "Lightmatter"),
    ("psiquantum",         "PsiQuantum"),
    ("figure",             "Figure"),
    ("agilityrobotics",    "Agility Robotics"),
    # added October 2026, each checked live against its job board
    ("optiverus", "Optiver"),
    ("wehrtyou", "Hudson River Trading"),
    ("drweng", "DRW"),
    ("fiveringsllc", "Five Rings"),
    ("squarepointcapital", "Squarepoint Capital"),
    ("quberesearchandtechnologies", "Qube Research & Technologies"),
    ("towerresearchcapital", "Tower Research Capital"),
    ("schonfeld", "Schonfeld"),
    ("oldmissioncapital", "Old Mission"),
    ("quadraturecapital", "Quadrature Capital"),
    ("point72", "Point72"),
    ("jumptrading", "Jump Trading"),
    ("gsacapital", "GSA Capital"),
    ("mangroup", "Man Group"),
    ("virtu", "Virtu Financial"),
    ("xtxmarketstechnologies", "XTX Markets"),
    ("akunacapital", "Akuna Capital"),
    ("flowtraders", "Flow Traders"),
    ("deliveroo", "Deliveroo"),
    ("netcraft", "Netcraft"),
    ("ionq", "IonQ"),
    ("isomorphiclabs", "Isomorphic Labs"),
    ("dexory", "Dexory"),
    ("mindfoundry", "Mind Foundry"),
    ("planetlabs", "Planet"),
    ("purestorage", "Pure Storage"),
    ("gocardless", "GoCardless"),
    ("complyadvantage", "ComplyAdvantage"),
    ("ebury", "Ebury"),
    ("tide", "Tide"),
    ("sumup", "SumUp"),
    ("blockchain", "Blockchain.com"),
    ("gymshark", "Gymshark"),
    ("ohme", "Ohme"),
    ("zscaler", "Zscaler"),
    ("wizinc", "Wiz"),
    ("netskope", "Netskope"),
    ("pingidentity", "Ping Identity"),
    ("beyondtrust", "BeyondTrust"),
    ("abnormalsecurity", "Abnormal Security"),
    ("recordedfuture", "Recorded Future"),
    ("chainguard", "Chainguard"),
    ("grafanalabs", "Grafana Labs"),
    ("tailscale", "Tailscale"),
    ("bitwarden", "Bitwarden"),
]

# Lever slugs confirmed to return HTTP 200 with real listings.
LEVER_COMPANIES = [
    ("palantir",     "Palantir"),
    ("wealthsimple", "Wealthsimple"),
    ("cloudinary",   "Cloudinary"),
    ("spotify",      "Spotify"),
    # robotic manipulation - verified live July 2026.
    ("dexterity",    "Dexterity"),
    # added October 2026, each checked live against its job board
    ("cirrus", "Cirrus Logic"),
    ("quantinuum", "Quantinuum"),
    ("octoenergy", "Octopus Energy"),
    ("zopa", "Zopa"),
    ("scottlogic", "Scott Logic"),
    ("sophos", "Sophos"),
    ("shieldai", "Shield AI"),
    ("matillion", "Matillion"),
    ("farfetch", "Farfetch"),
]

# (ashby_slug, display_name) - confirmed against live API.
ASHBY_COMPANIES = [
    ("linear",          "Linear"),
    ("perplexity",      "Perplexity AI"),
    ("cursor",          "Cursor"),
    ("vercel",          "Vercel"),
    ("railway",         "Railway"),
    ("loom",            "Loom"),
    ("supabase",        "Supabase"),
    ("neon",            "Neon"),
    ("openai",          "OpenAI"),
    ("anyscale",        "Anyscale"),
    # removed July 2026 after a full live sweep: iter, mistralai, huggingface,
    # turso, planetscale, deepmind and waymo all 404 on the Ashby board API now
    # (migrated or renamed). DeepMind arrives via the Google Careers scraper and
    # Mistral, Hugging Face and Waymo stay on the priority list so the boards
    # still catch them.
    # expanded - all confirmed against live API (June 2026)
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
    # wayve is also on Greenhouse (118 jobs) but Ashby has description/dates.
    ("wayve",           "Wayve"),
    # confirmed live July 2026 - Cerebras is the most relevant AI hardware company.
    ("cerebras",        "Cerebras"),
    ("cognition",       "Cognition"),
    ("ramp",            "Ramp"),
    # AI-accelerator and robotics silicon, each verified live July 2026. Axelera
    # is an Eindhoven edge-AI chip firm; Etched builds transformer ASICs; Physical
    # intelligence builds robot foundation models. Their software roles come too.
    ("axelera",             "Axelera AI"),
    ("etched",              "Etched"),
    ("physicalintelligence", "Physical Intelligence"),
    # added October 2026, each checked live against its job board
    ("lendable", "Lendable"),
    ("humanoid", "Humanoid"),
    ("faculty", "Faculty"),
    ("fractile", "Fractile"),
    ("krakentech", "Kraken Technologies"),
    ("checkout.com", "Checkout.com"),
    ("cleo-2", "Cleo"),
    ("trainline", "Trainline"),
    ("synthesia", "Synthesia"),
    ("elevenlabs", "ElevenLabs"),
    ("quantexa", "Quantexa"),
    ("snyk", "Snyk"),
    ("1password", "1Password"),
    ("vanta", "Vanta"),
    ("cyberhaven", "Cyberhaven"),
    ("delinea", "Delinea"),
    ("drata", "Drata"),
    ("socure", "Socure"),
    ("lumai", "Lumai"),
    ("olix", "Olix"),
    ("salience-labs", "Salience Labs"),
    ("vertical-aerospace", "Vertical Aerospace"),
    ("applied", "Applied Intuition"),
    ("allica-bank", "Allica Bank"),
    ("oaknorth", "OakNorth"),
    ("moneybox", "Moneybox"),
    ("clearbank", "ClearBank"),
    ("fundingcircle", "Funding Circle"),
    ("multiverse", "Multiverse"),
    ("airwallex", "Airwallex"),
    ("motorway", "Motorway"),
    ("paddle", "Paddle"),
    ("pleo", "Pleo"),
    ("duffel", "Duffel"),
    ("elliptic", "Elliptic"),
    ("zilch", "Zilch"),
]

# SmartRecruiters, rebuilt July 2026 after a full live sweep: every one of the 26
# old identifiers returned totalFound 0 (the API answers a valid empty envelope for
# unknown tenants rather than a 404, so the whole list was silently contributing
# nothing). These are the tenants that verifiably return postings on the anonymous
# API today; Version1 is a major UK and Ireland placement employer.
EIGHTFOLD_COMPANIES = [
    # (tenant, domain, display_name) for the Eightfold public jobs API. STMicro
    # is a major semiconductor maker with a UK design centre in Edinburgh, exactly
    # the embedded and hardware placements in scope; verified live July 2026
    # (514 positions). Eightfold is a whole ATS platform, so more tenants can join
    # this list once their exact slug is verified.
    ("stmicroelectronics", "stmicroelectronics.com", "STMicroelectronics"),
    # added October 2026, each checked live against its job board
    ("mlp", "mlp.com", "Millennium"),
    ("hsbc", "hsbc.com", "HSBC"),
]

# (slug, display_name) for the Workable widget API - the UK deep-tech startups
# that never post on the big boards: defence AI (Arondite), satcom terminals
# (ALL.SPACE), power electronics (IONATE), education hardware (Micro:bit).
# every slug probed live July 2026; a tenant with zero openings today
# (Marshmallow, Oxa) stays because the probe costs one request and their
# student roles appear seasonally.
WORKABLE_COMPANIES = [
    ("arondite",                         "Arondite"),
    ("allspace",                         "ALL.SPACE"),
    ("ionate",                           "IONATE"),
    ("micro-bit-educational-foundation", "Micro:bit Foundation"),
    ("homey",                            "Homey"),
    ("marshmallow",                      "Marshmallow"),
    ("oxa",                              "Oxa"),
    # added October 2026, each checked live against its job board
    ("starling-bank", "Starling Bank"),
    ("universalquantum", "Universal Quantum"),
    ("nu-quantum", "Nu Quantum"),
    ("tokamak-energy", "Tokamak Energy"),
    ("zeroavia", "ZeroAvia"),
    ("bridewell", "Bridewell"),
    ("ripjar", "Ripjar"),
    ("aegiq", "Aegiq"),
    ("habitat-energy", "Habitat Energy"),
]

# (slug, display_name) for the Recruitee offers API, probed live July 2026:
# lucid Games (Liverpool studio), DeepHealth and BCN Group answered with live
# postings; the rest are valid UK tenants currently between openings.
RECRUITEE_COMPANIES = [
    ("lucidgames",      "Lucid Games"),
    ("deephealth",      "DeepHealth"),
    ("bcngroup",        "BCN Group"),
    ("evergreenenergy", "Evergreen Energy"),
    ("getchip",         "Chip"),
    ("citymapper",      "Citymapper"),
    ("zeelo",           "Zeelo"),
]

# (feed_host, display_name) for the Personio XML feed. Quantum Motion is a
# London quantum-computing company designing cryogenic silicon qubit chips -
# exactly the kind of UK deep-tech hardware employer the list is for.
PERSONIO_COMPANIES = [
    ("quantummotion.jobs.personio.com", "Quantum Motion"),
]

# (careers_host, display_name) for the Jibe/iCIMS careers API. AMD's UK site
# (the former Xilinx design centres) posts its student roles here seasonally;
# today it lists 17 UK silicon roles and the intern postings join them each
# autumn.
JIBE_COMPANIES = [
    ("careers.amd.com", "AMD"),
]

SMARTRECRUITERS_COMPANIES = [
    ("ServiceNow", "ServiceNow"),
    ("Experian",   "Experian"),
    ("Ubisoft2",   "Ubisoft"),
    ("Version1",   "Version 1"),
    ("Visa",       "Visa"),
    # added October 2026, each checked live against its job board
    ("BoschGroup", "Bosch"),
    ("RenesasElectronics", "Renesas"),
    ("Wise", "Wise"),
    ("WilliamsRacing", "Williams Racing"),
    ("LegalAndGeneral", "Legal & General"),
    ("Endava", "Endava"),
]
