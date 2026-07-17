"""Cloudflare-resistant fetch for the student boards that block plain requests.

Gradcracker, Bright Network and Milkround sit behind Cloudflare, which rejects
the requests library on its TLS fingerprint alone (a 403 before any page loads),
yet they server-render their job listings as ordinary HTML. curl_cffi replays a
real Chrome TLS and HTTP2 fingerprint, so the same GET that requests cannot make
comes back 200. This is far cheaper and steadier than a headless browser, which
Cloudflare blocks anyway from a data-centre IP on the navigator.webdriver signal.

I keep this in its own module so the import is optional: if curl_cffi is missing
the helper returns an empty string rather than raising, so a source degrades to
zero rows instead of taking the whole run down.
"""

try:
    from curl_cffi import requests as _cffi
    _AVAILABLE = True
except Exception:  # pragma: no cover - exercised only where the dep is absent
    _cffi = None
    _AVAILABLE = False

# I pin a recent Chrome fingerprint; the boards' Cloudflare rules accept it and
# it matches the User-Agent the impersonation sends, so the two never disagree.
_IMPERSONATE = "chrome"


def browser_get(url: str, params: "dict | None" = None, timeout: int = 25) -> str:
    """Return the page HTML with a browser TLS fingerprint, or "" on any failure.

    A non-200, a missing dependency or a network error all return "" so the
    caller simply finds no jobs that run rather than crashing the scraper.
    """
    if not _AVAILABLE:
        print("  [browser] curl_cffi not installed - skipping")
        return ""
    try:
        resp = _cffi.get(
            url,
            params=params,
            impersonate=_IMPERSONATE,
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            print(f"  [browser] {url}: HTTP {resp.status_code}")
            return ""
        return resp.text
    except Exception as e:
        print(f"  [browser] {url}: {e}")
        return ""
