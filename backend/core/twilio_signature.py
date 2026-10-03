"""
X-Twilio-Signature validation for the Twilio webhooks.

Nothing checked that a POST to /twilio/voice or /api/voice/twiml came from
Twilio. Those handlers trust `From` (rate limits, transcripts, the caller
identity handed to the stream) and, since core/stream_auth.py, they mint the
stream token — so an unsigned webhook would hand an attacker a valid token
for any number they type. This closes that.

Twilio signs the exact public URL it requested (scheme, host, path, query)
plus the sorted form params, with the account auth token.

Gated by settings.TWILIO_SIGNATURE_MODE ("off" | "report" | "enforce"), for
the same reason as STREAM_AUTH_MODE: ship in "report", read the verdict
lines on a real call, then enforce.
"""
import logging

import sentry_sdk
from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from core.config import settings
from core.stream_auth import log_once, resolve_mode

logger = logging.getLogger(__name__)


def twilio_signature_mode() -> str:
    """Effective mode; degrades to "off" (one ERROR) without TWILIO_AUTH_TOKEN."""
    mode = resolve_mode("TWILIO_SIGNATURE_MODE")
    if mode != "off" and not settings.TWILIO_AUTH_TOKEN:
        log_once(
            "twilio-sig:notoken", logging.ERROR,
            "🔐 [TwilioSig] TWILIO_AUTH_TOKEN is not set — webhook signature validation is OFF",
            log=logger,
        )
        return "off"
    return mode


def public_url(request: Request) -> str:
    """
    The URL Twilio actually called. Heroku's router terminates TLS, so the
    app sees `http://` in request.url while Twilio signed `https://…`; the
    scheme has to come from X-Forwarded-Proto (first hop, if a chain). Host
    is passed through unchanged by the router, and Heroku does not append a
    port, so request.url's netloc is the public host. The validator itself
    retries with and without :443, covering either form.
    """
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    url = f"{proto}://{request.url.netloc}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    return url


async def verify_twilio_signature(request: Request) -> None:
    """
    FastAPI dependency. Raises 403 only in "enforce"; otherwise it logs the
    verdict and returns, so the route runs exactly as it did before.
    """
    mode = twilio_signature_mode()
    path = request.url.path
    if mode == "off":
        return

    signature = request.headers.get("x-twilio-signature")
    url = public_url(request)
    if not signature:
        verdict = "missing"
    else:
        # Starlette caches the parsed form on the request, so the route's own
        # Form(...) parameters read the same body without consuming it twice.
        params = await request.form() if request.method == "POST" else {}
        valid = RequestValidator(settings.TWILIO_AUTH_TOKEN).validate(url, params, signature)
        verdict = "valid" if valid else "invalid"

    logger.info("🔐 [TwilioSig] verdict=%s mode=%s path=%s", verdict, mode, path)
    if verdict == "valid":
        return

    action = "rejecting" if mode == "enforce" else "allowing (report mode)"
    # The URL we checked against, minus the query (it can carry a phone
    # number): a scheme/host mismatch is the likeliest false "invalid".
    msg = f"[TwilioSig] {verdict} X-Twilio-Signature on {url.split('?')[0]} — {action}"
    logger.warning("🔐 %s", msg)
    try:
        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass
    if mode == "enforce":
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
