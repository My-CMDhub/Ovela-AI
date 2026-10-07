"""
Signed stream tokens for Twilio Media Streams.

`/api/voice/stream` is a public WebSocket, and everything the agent knows
about who is calling comes from the `start` message's customParameters —
which the client writes. Without a check, anyone who knows the URL can open
the socket, claim a guest's phone number, and pass every "caller owns this
booking" gate (guest PII, payment-link resends) on our LLM/TTS bill.

The fix: the TwiML we return carries a `stream_token` <Parameter>, an HMAC
over the exact call_sid/user_phone/tenant_id it was issued for. Twilio echoes
it back in `start`; we recompute it there. Only a party that received our
TwiML — i.e. Twilio, once webhook signatures are enforced — can hold one.

Rollout is gated by settings.STREAM_AUTH_MODE ("off" | "report" | "enforce")
because nobody can test a live call before this ships: "report" logs and
lets everything through, so a bug here cannot drop a real call.
"""
import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64encode
from typing import Optional, Tuple

import sentry_sdk

from core.config import settings

logger = logging.getLogger(__name__)

MODES = ("off", "report", "enforce")

# Twilio opens the stream within a second or two of fetching the TwiML. Ten
# minutes is headroom for slow TwiML fetches and dyno clock drift, while
# still bounding how long a leaked token is worth anything.
TOKEN_TTL_S = 600
# Issue and verify can run on different dynos; tolerate their clocks
# disagreeing by this much in the "issued in the future" direction.
CLOCK_SKEW_S = 30

_VERSION = "v1"
# Domain-separation label: the base secret is shared with the magic links, so
# the key actually used here is HMAC(base, label). A token from one system can
# never verify in the other.
_KEY_LABEL = b"ovela/stream-token/v1"

# Log-once guards. A misconfiguration is worth one loud line, not one per call.
_logged_once: set = set()


def log_once(key: str, level: int, msg: str, *args, log: Optional[logging.Logger] = None) -> None:
    if key in _logged_once:
        return
    _logged_once.add(key)
    (log or logger).log(level, msg, *args)


def resolve_mode(setting_name: str) -> str:
    """
    Read an off/report/enforce setting at call time (so it can be flipped by
    a config change and patched in tests). Anything unrecognised is treated
    as "report": a typo must never become either "reject every call" or
    "silently check nothing".
    """
    raw = str(getattr(settings, setting_name, "report") or "").strip().lower()
    if raw in MODES:
        return raw
    log_once(
        f"mode:{setting_name}:{raw}", logging.WARNING,
        "🔐 %s=%r is not one of off/report/enforce — behaving as 'report'",
        setting_name, raw,
    )
    return "report"


def _signing_key() -> Optional[bytes]:
    """
    STREAM_TOKEN_SECRET if set, else the magic-link secret chain
    (MAGIC_LINK_SECRET, then APPWRITE_API_KEY — see services/magic_links.py),
    so no new env var is required to roll this out. The magic-link module's
    last-resort "default-secret-key" literal is deliberately NOT reused: a
    key that is in the source code signs nothing.
    """
    base = (
        getattr(settings, "STREAM_TOKEN_SECRET", "")
        or getattr(settings, "MAGIC_LINK_SECRET", None)
        or getattr(settings, "APPWRITE_API_KEY", "")
    )
    if not base:
        return None
    return hmac.new(base.encode("utf-8"), _KEY_LABEL, hashlib.sha256).digest()


def stream_auth_mode() -> str:
    """Effective mode; degrades to "off" (one ERROR) when no secret exists."""
    mode = resolve_mode("STREAM_AUTH_MODE")
    if mode != "off" and _signing_key() is None:
        log_once(
            "stream:nokey", logging.ERROR,
            "🔐 [StreamAuth] No STREAM_TOKEN_SECRET / magic-link secret configured — "
            "stream authentication is OFF",
        )
        return "off"
    return mode


def _mac(key: bytes, iat: int, bound: bool, call_sid: str, user_phone: str, tenant_id: str) -> str:
    # JSON list as the canonical encoding: unambiguous whatever characters the
    # fields contain, unlike joining on a separator a phone/tenant could hold.
    payload = json.dumps(
        [_VERSION, iat, "b" if bound else "u", call_sid if bound else "", user_phone or "", tenant_id or ""],
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def issue_stream_token(call_sid: Optional[str], user_phone: str, tenant_id: str, now: Optional[float] = None) -> str:
    """
    Token for the `stream_token` <Parameter>: "v1.<issued_at>.<b|u>.<mac>".

    Sign the values exactly as they go into the TwiML — Twilio echoes the
    parameters back unescaped, and verify compares against those.

    Returns "" when there is no key; the start handler then reports "missing",
    which in "off" (the only mode a keyless server can be in) is ignored.
    """
    key = _signing_key()
    if key is None:
        return ""
    iat = int(time.time() if now is None else now)
    # Bound to the CallSid whenever we have one. Both producers always get one
    # from Twilio today, but /api/voice/twiml reads it defensively, so a token
    # minted without a CallSid is marked "u" (unbound) — and that marker is
    # inside the MAC, so nobody can strip the binding off a bound token. An
    # unbound token still pins phone + tenant + expiry, which is what the
    # privacy gates key on.
    bound = bool(call_sid)
    return f"{_VERSION}.{iat}.{'b' if bound else 'u'}.{_mac(key, iat, bound, call_sid or '', user_phone, tenant_id)}"


def verify_stream_token(
    token: Optional[str],
    call_sid: Optional[str],
    user_phone: str,
    tenant_id: str,
    now: Optional[float] = None,
) -> Tuple[bool, str]:
    """(ok, reason). reason is "valid", "valid-unbound", "missing" or why it failed."""
    if not token:
        return False, "missing"
    key = _signing_key()
    if key is None:
        return False, "no-key"
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _VERSION or parts[2] not in ("b", "u"):
        return False, "malformed"
    try:
        iat = int(parts[1])
    except ValueError:
        return False, "malformed"
    bound = parts[2] == "b"
    expected = _mac(key, iat, bound, call_sid or "", user_phone, tenant_id)
    # Constant-time: the MAC is the secret-dependent part.
    if not hmac.compare_digest(expected.encode("ascii"), parts[3].encode("ascii", "replace")):
        return False, "bad-signature"
    # Expiry only after the MAC: iat is attacker-supplied until the MAC
    # proves we wrote it.
    current = time.time() if now is None else now
    if iat > current + CLOCK_SKEW_S:
        return False, "issued-in-future"
    if current - iat > TOKEN_TTL_S:
        return False, "expired"
    return True, "valid" if bound else "valid-unbound"


def check_stream_start(start: dict) -> bool:
    """
    Judge a Twilio `start` payload. Returns False only when the call must be
    rejected (mode "enforce" and the token is missing or invalid).

    Logs the verdict at INFO on every call — that line is how the owner
    confirms "valid" on a real call before switching to enforce.
    """
    mode = stream_auth_mode()
    params = (start or {}).get("customParameters") or {}
    call_sid = (start or {}).get("callSid", "") or ""
    if mode == "off":
        logger.info("🔐 [StreamAuth] verdict=skipped mode=off call=%s", call_sid or "-")
        return True

    ok, reason = verify_stream_token(
        params.get("stream_token"),
        call_sid,
        params.get("user_phone", "") or "",
        params.get("tenant_id", "") or "",
    )
    verdict = "valid" if ok else ("missing" if reason == "missing" else "invalid")
    logger.info(
        "🔐 [StreamAuth] verdict=%s reason=%s mode=%s call=%s",
        verdict, reason, mode, call_sid or "-",
    )
    if ok:
        return True

    action = "rejecting" if mode == "enforce" else "allowing (report mode)"
    msg = f"[StreamAuth] {verdict} stream token ({reason}) on call {call_sid or '-'} — {action}"
    logger.warning("🔐 %s", msg)
    try:
        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass
    return mode != "enforce"
