"""
Headers for pages whose URL carries a magic-link token (?token=…).

A link on such a page ("Open Dashboard") sent the full URL, token included, to
the next site in the Referer header, and a shared browser could serve it back
from cache. The confirm pages set these headers themselves; this middleware
covers the POST result pages and anything added later under the same prefixes.
"""

TOKEN_URL_PREFIXES = ("/api/actions/", "/actions/", "/api/voice/demo-")


async def no_referrer_on_token_pages(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(TOKEN_URL_PREFIXES):
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
    return response
