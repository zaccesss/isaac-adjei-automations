"""Location vocabulary and the UK-and-Europe location filter."""


# UK and major European tech hubs - broad enough to catch all UK roles and
# nearby European offices that UK students commonly get placed to.
UK_EU_TERMS = [
    # UK national terms
    "uk", "united kingdom", "england", "scotland", "wales",
    "great britain", "britain", "gb", "u.k.",
    # London and Greater London boroughs
    "london", "canary wharf", "croydon", "ilford", "bromley", "harrow",
    "sutton", "kingston upon thames", "richmond", "wimbledon", "stratford",
    "greenwich", "hackney", "islington", "lambeth", "southwark", "wandsworth",
    "shoreditch", "hoxton", "bank", "city of london", "westminster",
    # More London districts that postings actually name, so a London role is
    # never dropped for using a neighbourhood instead of the city.
    "kings cross", "king's cross", "paddington", "liverpool street",
    "moorgate", "holborn", "farringdon", "soho", "covent garden", "camden",
    "hammersmith", "euston", "old street", "aldgate", "canada water",
    "white city", "brixton", "battersea", "vauxhall", "ealing", "wembley",
    # Major UK cities
    "birmingham", "manchester", "edinburgh", "glasgow", "bristol",
    "cambridge", "oxford", "reading", "leeds", "sheffield",
    "liverpool", "nottingham", "coventry", "leicester", "southampton",
    "portsmouth", "exeter", "bath", "brighton", "norwich", "york",
    "cardiff", "belfast", "newcastle", "sunderland", "middlesbrough",
    "hull", "stoke", "wolverhampton", "derby", "worcester",
    "milton keynes", "luton", "slough", "guildford", "basingstoke",
    "watford", "hertford", "ipswich", "chelmsford", "stevenage",
    "guildford", "guildford", "woking", "farnborough", "eastleigh",
    "solihull", "walsall", "west bromwich", "dudley", "sandwell",
    "salford", "stockport", "oldham", "rochdale", "bolton", "trafford",
    # Remote / flexible
    "remote", "work from home", "hybrid", "flexible", "distributed",
    "anywhere in the uk", "home based", "home-based",
    # Republic of Ireland (many UK students work in Dublin)
    "ireland", "dublin",
    # Key European tech hubs
    "amsterdam", "berlin", "munich", "paris", "lisbon",
    "madrid", "barcelona", "stockholm", "zurich", "geneva",
    "brussels", "luxembourg",
    # Generic region terms
    "europe", "emea", "european", "worldwide", "global",
    "nationwide",
    # Asia-Pacific tech hubs - UK students commonly target these
    "singapore", "sydney", "melbourne", "australia",
    "hong kong",
]

# Explicitly US/non-EU locations - always rejected even for priority companies.
US_LOCATIONS = [
    "new york", "san francisco", "los angeles", "san jose",
    "seattle", "boston", "chicago", "austin", "denver", "atlanta",
    "miami", "dallas", "philadelphia", "portland", "minneapolis",
    "raleigh", "charlotte", "salt lake city", "phoenix", "las vegas",
    "california", "new jersey", "texas", "north carolina", "colorado",
    "washington, dc", "washington d.c.", "washington, d.c.",
    "united states", "usa", "u.s.a", "u.s.", "north america",
    # Canada (separate from UK/EU)
    "toronto", "vancouver", "montreal", "canada",
    # Asia-Pacific
    "tokyo", "bangalore", "hyderabad", "india", "china",
    # Exclude honolulu, hawaii specifically
    "honolulu", "hawaii",
    # I add these normalised remote-US strings because the scraper lowercases
    # location before matching and these variants were slipping through.
    "remote - us", "remote, us", "us remote", "remote us",
    # I add specific US cities missing from the original list.
    "palo alto", "menlo park", "mountain view", "sunnyvale", "cupertino",
    "redmond", "bellevue", "kirkland", "san diego", "irvine",
    "gurugram", "gurgaon",
]

# Known standalone UK city names used for location normalisation.
# When a posting says just "London" we store it as "London, UK".
UK_CITIES = {
    "london", "birmingham", "manchester", "edinburgh", "glasgow",
    "bristol", "cambridge", "oxford", "reading", "leeds", "sheffield",
    "liverpool", "nottingham", "coventry", "leicester", "southampton",
    "portsmouth", "exeter", "bath", "brighton", "norwich", "york",
    "cardiff", "belfast", "newcastle upon tyne", "newcastle",
    "milton keynes", "guildford", "basingstoke", "watford",
    "wolverhampton", "derby", "worcester", "ipswich",
}


def normalize_location(location: str) -> str:
    """Append ', UK' to bare UK city names that lack a country suffix.

    Greenhouse/Lever often return just "London" or "Birmingham". I append
    ', UK' so the table clearly shows the country.
    """
    if not location:
        return location
    stripped = location.strip()
    lower = stripped.lower()
    # Already has a country or region indicator - leave as is
    if any(c in lower for c in [
        "uk", "united kingdom", "england", "scotland", "wales",
        "remote", "hybrid", "europe", "emea", "global", "worldwide",
        "ireland", "berlin", "amsterdam", "paris", "lisbon", "zurich",
    ]):
        return stripped
    # Known bare UK city - append ", UK"
    for city in UK_CITIES:
        if city in lower:
            return f"{stripped}, UK"
    return stripped


def is_location_ok(location: str, is_priority: bool) -> bool:
    """True if the location is UK/Europe or unknown.

    I accept all of UK (any city), Remote/Hybrid and major European tech
    hubs. I reject explicit US locations for all companies regardless of
    tier. For priority companies I also accept unknown/unrecognised foreign
    locations because they likely have UK offices not labelled in every post.
    """
    if not location:
        return True  # unknown = include
    loc = location.lower()
    # I also reject locations that end with ", us" because some postings
    # use that pattern instead of spelling out "United States".
    if loc.rstrip().endswith(", us"):
        return False
    # Explicit US/non-EU = always reject
    if any(us in loc for us in US_LOCATIONS):
        return False
    # UK / EU match = accept
    if any(uk in loc for uk in UK_EU_TERMS):
        return True
    # Priority company + unrecognised foreign location = accept
    return is_priority
