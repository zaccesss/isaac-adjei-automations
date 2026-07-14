"""Shared browser-impersonating headers and the URL liveness check."""

import requests

# I impersonate a real Chrome browser so sites do not block the scraper with
# a bot check. Accept-Language hints I am a UK user, biasing geo results.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


def is_url_alive(url: str) -> bool:
    """Return False only if the URL definitively 404s or 410s (gone for good).

    I use a HEAD request so no body is transferred - fast enough to run per
    job. On any network error I assume the URL is alive rather than silently
    dropping valid roles.
    """
    if not url or not url.startswith("http"):
        return True
    try:
        resp = requests.head(url, headers=HEADERS, timeout=8,
                             allow_redirects=True)
        # Some servers don't support HEAD and return 405 - fall back to GET.
        if resp.status_code == 405:
            resp = requests.get(url, headers=HEADERS, timeout=10,
                                allow_redirects=True, stream=True)
            resp.close()
        return resp.status_code not in (404, 410)
    except Exception:
        return True  # network issue - assume alive
