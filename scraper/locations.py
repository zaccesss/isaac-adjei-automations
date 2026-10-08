"""Location vocabulary and the UK-and-Europe location filter."""
import re


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
    # more London districts that postings actually name, so a London role is
    # never dropped for using a neighbourhood instead of the city.
    "kings cross", "king's cross", "paddington", "liverpool street",
    "moorgate", "holborn", "farringdon", "soho", "covent garden", "camden",
    "hammersmith", "euston", "old street", "aldgate", "canada water",
    "white city", "brixton", "battersea", "vauxhall", "ealing", "wembley",
    # major UK cities
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
    # remote / flexible
    "remote", "work from home", "hybrid", "flexible", "distributed",
    "anywhere in the uk", "home based", "home-based",
    # republic of Ireland (many UK students work in Dublin)
    "ireland", "dublin",
    # key European tech hubs
    "amsterdam", "berlin", "munich", "paris", "lisbon",
    "madrid", "barcelona", "stockholm", "zurich", "geneva",
    "brussels", "luxembourg",
    # generic region terms
    "europe", "emea", "european", "worldwide", "global",
    "nationwide",
    # Asia-Pacific tech hubs - UK students commonly target these
    "singapore", "sydney", "melbourne", "australia",
    "hong kong",
]

# explicitly US/non-EU locations - always rejected even for priority companies.
US_LOCATIONS = [
    "new york", "san francisco", "los angeles", "san jose",
    "seattle", "boston", "chicago", "austin", "denver", "atlanta",
    "miami", "dallas", "philadelphia", "portland", "minneapolis",
    "raleigh", "charlotte", "salt lake city", "phoenix", "las vegas",
    "california", "new jersey", "texas", "north carolina", "colorado",
    "washington, dc", "washington d.c.", "washington, d.c.",
    "united states", "usa", "u.s.a", "u.s.", "north america",
    # canada (separate from UK/EU)
    "toronto", "vancouver", "montreal", "canada",
    # Asia-Pacific
    "tokyo", "bangalore", "bengaluru", "hyderabad", "india", "china",
    # exclude honolulu, hawaii specifically
    "honolulu", "hawaii",
    # add these normalised remote-US strings because the scraper lowercases
    # location before matching and these variants were slipping through.
    "remote - us", "remote, us", "us remote", "remote us",
    # add specific US cities missing from the original list.
    "palo alto", "menlo park", "mountain view", "sunnyvale", "cupertino",
    "redmond", "bellevue", "kirkland", "san diego", "irvine",
    "gurugram", "gurgaon",
]

# known standalone UK city names used for location normalisation.
# when a posting says just "London" we store it as "London, UK".
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
    # already has a country or region indicator - leave as is
    if any(c in lower for c in [
        "uk", "united kingdom", "england", "scotland", "wales",
        "remote", "hybrid", "europe", "emea", "global", "worldwide",
        "ireland", "berlin", "amsterdam", "paris", "lisbon", "zurich",
    ]):
        return stripped
    # a bare UK city gains ", UK"; whole words and the foreign-namesake check stop
    # "New York" becoming "New York, UK"
    if is_uk(stripped):
        return f"{stripped}, UK"
    return stripped


# the dashboard and Vitafolio list UK roles only. A place counts when it names the UK or a UK town;
# a same-named town abroad (Sydney's New South Wales, Durham NC, Chester VA) is caught by _NOT_UK.
_UK_RE = re.compile(
    r"\b(uk|u\.k\.|united kingdom|great britain|gb|england|scotland|wales|northern ireland|"
    r"london|birmingham|manchester|edinburgh|glasgow|bristol|cambridge|oxford|reading|leeds|"
    r"sheffield|liverpool|nottingham|coventry|leicester|southampton|portsmouth|exeter|bath|"
    r"brighton|norwich|york|cardiff|belfast|newcastle|milton keynes|guildford|basingstoke|"
    r"watford|wolverhampton|derby|worcester|ipswich|aberdeen|dundee|swansea|bournemouth|"
    r"cheltenham|bracknell|slough|stevenage|crawley|warrington|chester|lincoln|plymouth|"
    r"sunderland|durham|loughborough|harwell|didcot|filton|farnborough|bedford|luton|knutsford|"
    r"preston|chelmsford|newport|colchester|swindon|gloucester|hull|solihull|telford|stockport|"
    r"salford|stafford|stoke|northampton|peterborough|woking|maidenhead|uxbridge|livingston|"
    r"stirling|inverness|lisburn|derry|londonderry|newry|yeovil|lancaster|havant|sandhurst|fleet|camberley|"
    r"aldershot|winchester|salisbury|taunton|truro|canterbury|maidstone|tunbridge wells|high wycombe|"
    r"aylesbury|st albans|hatfield|harlow|basildon|southend|cambourne|warwick|leamington|kenilworth|rugby|"
    r"nuneaton|tamworth|lichfield|chesterfield|mansfield|doncaster|rotherham|barnsley|wakefield|"
    r"huddersfield|bradford|halifax|harrogate|middlesbrough|darlington|gateshead|carlisle|kendal|"
    r"blackburn|bolton|wigan|oldham|rochdale|macclesfield|altrincham|runcorn|widnes|deeside|wrexham|"
    r"bangor|bridgend|llanelli|pontypridd|falkirk|kilmarnock|paisley|east kilbride|cumbernauld|rosyth|"
    r"dunfermline|kirkcaldy|craigavon|ballymena|newtownabbey|gosport|fareham|eastleigh|romsey|poole|"
    r"weymouth|barnstaple|torquay|hereford|shrewsbury|worthing|horsham|chichester|eastbourne|hastings|"
    r"ashford|dover|folkestone|sevenoaks|dartford|hitchin|letchworth|welwyn|hemel hempstead|cirencester|"
    r"tewkesbury|stroud|abingdon|bicester|banbury|witney|marlow|wokingham|newbury|thatcham|chippenham|"
    r"trowbridge|corsham|bridgwater|kettering|corby|wellingborough|daventry|grantham|scunthorpe|grimsby|"
    r"thetford|bury st edmunds|lowestoft|felixstowe|braintree|harwich)\b",
    re.IGNORECASE,
)
_NOT_UK = re.compile(
    r"new south wales|australia|ontario|canada|new york|new jersey|new hampshire|new england|massachusetts|"
    r"pennsylvania|virginia|carolina|\busa\b|united states|^us\b|\bus,|"
    r", (al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|"
    r"ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)\b",
    re.IGNORECASE,
)
# a board's placeholder for a listing posted in several places, with no place named
MULTI_LOCATION_RE = re.compile(r"^\s*\d+\s+locations?\s*$", re.IGNORECASE)


def is_uk(location: str) -> bool:
    """True only when the location names somewhere in the UK; unknown places are not assumed."""
    if not location:
        return False
    if _UK_RE.search(location) and not _NOT_UK.search(location):
        return True
    # a listing that names London among other cities is still a London role
    return bool(re.search(r"\blondon\b", location, re.IGNORECASE)) and not re.search(r"ontario|canada", location, re.IGNORECASE)


def is_location_ok(location: str, is_priority: bool = False) -> bool:
    """True for a UK location or an unknown one; the final check in insert_job settles unknowns.

    UK only since October 2026: Europe and priority companies' foreign offices are no longer
    accepted. is_priority is kept so existing callers need no change.
    """
    if not location:
        return True
    return is_uk(location)
