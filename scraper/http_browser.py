"""Cloudflare-resistant fetch for the student boards that block plain requests.

Gradcracker, Bright Network and Milkround sit behind Cloudflare, which rejects the
requests library on its TLS fingerprint alone (a 403 before any page loads), yet
they server-render their job listings as ordinary HTML. I try two layers:

1. curl_cffi replays a real Chrome TLS and HTTP2 fingerprint. This clears
   Cloudflare's fingerprint check and is fast, so it is the first attempt. It is
   enough for Gradcracker and works from a home IP for all three.
2. When curl_cffi still gets a 403 - which happens from a data-centre IP, where
   Cloudflare's IP reputation adds a managed Turnstile challenge on top - I fall
   back to Scrapling's StealthyFetcher, a real Camoufox browser that solves the
   challenge. A CI experiment confirmed this reaches Bright Network and Milkround
   from a GitHub Actions runner where curl_cffi is blocked, so it needs no proxy
   and no external VM. It is slow (a browser boot plus a solve per page), which is
   why it is only the fallback.

Both layers are optional imports: if a dependency is missing the layer is skipped,
so a source degrades to zero rows rather than taking the whole run down.
"""
from urllib.parse import urlencode

try:
    from curl_cffi import requests as _cffi
    _CFFI_OK = True
except Exception:  # pragma: no cover - exercised only where the dep is absent
    _cffi = None
    _CFFI_OK = False

_IMPERSONATE = "chrome"


def _full_url(url: str, params: "dict | None") -> str:
    return f"{url}?{urlencode(params)}" if params else url


def _curl_cffi_get(url: str, params: "dict | None", timeout: int) -> "tuple[str, int]":
    """Return (html, status). status 0 means the attempt could not run."""
    if not _CFFI_OK:
        return "", 0
    try:
        resp = _cffi.get(
            url,
            params=params,
            impersonate=_IMPERSONATE,
            timeout=timeout,
            allow_redirects=True,
        )
        return (resp.text if resp.status_code == 200 else ""), resp.status_code
    except Exception as e:
        print(f"  [curl_cffi] {url}: {e}")
        return "", 0


def _scrapling_get(url: str, params: "dict | None", wait_selector: "str | None" = None) -> str:
    """Fetch through Scrapling's Camoufox browser, solving Cloudflare, or ''.

    wait_selector holds the render until a matching element appears, which the
    JavaScript careers apps need because their jobs load after network idle.
    """
    try:
        from scrapling.fetchers import StealthyFetcher
    except Exception:
        print("  [scrapling] not installed - skipping fallback")
        return ""
    full = _full_url(url, params)
    kwargs = {"headless": True, "solve_cloudflare": True, "network_idle": True, "timeout": 90000}
    if wait_selector:
        kwargs["wait_selector"] = wait_selector
    try:
        page = StealthyFetcher.fetch(full, **kwargs)
        if getattr(page, "status", 0) == 200:
            return page.html_content or ""
        print(f"  [scrapling] {full}: status {getattr(page, 'status', '?')}")
        return ""
    except Exception as e:
        print(f"  [scrapling] {full}: {e}")
        return ""


def browser_get(url: str, params: "dict | None" = None, timeout: int = 25) -> str:
    """Return the page HTML, trying curl_cffi first then the Scrapling solver.

    For server-rendered pages behind Cloudflare (the student boards): curl_cffi
    returns the full HTML when it clears the fingerprint check, and only a block
    falls through to the browser solver. Any failure at both layers returns "".
    """
    html, status = _curl_cffi_get(url, params, timeout)
    if html:
        return html
    # A 403 (or a curl_cffi that could not run) means the fingerprint trick was
    # not enough; the browser solver is the fallback that clears the challenge.
    if status in (0, 403, 429, 503):
        return _scrapling_get(url, params)
    print(f"  [browser] {url}: HTTP {status}")
    return ""


def browser_render(url: str, params: "dict | None" = None, wait_selector: "str | None" = None) -> str:
    """Return the fully rendered HTML, always through the Scrapling browser.

    For JavaScript single-page careers sites (Google, Goldman Sachs) curl_cffi
    would return an empty shell with a 200, so it must not be tried first - the
    jobs only exist after the page's scripts run. This always renders and reads
    the populated DOM. Pass wait_selector to hold for a job element that loads
    late (Google's list arrives after network idle).
    """
    return _scrapling_get(url, params, wait_selector=wait_selector)
