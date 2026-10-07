"""
What happens when a caller asked for a person and did not get one.

Two places find out a transfer failed: the <Dial> action callback
(/twilio/transfer-status: no-answer, busy, failed, canceled) and the
orchestrator, when the Twilio REST call that starts the <Dial> raises. Before
this module both only logged, so staff never learned someone had tried to
reach them and the caller's "someone will call you back" was not true.

Both now go through `notify_failed_transfer`, which records a callback request
(staff_notifications row + email, the same path the request_human_callback tool
uses) and texts the staff phone (as the legacy handler.py did on transfer). It
NEVER raises: it runs beside a live call or after a Twilio webhook has already
answered, and a notification failure must not cost the caller anything.
"""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import settings
from core.utils import mask_phone

logger = logging.getLogger(__name__)

# ── What the live call says and remembers ───────────────────────────────────
# The pre-rendered `transfer_failed` clip's words, as the legacy handler paired
# them — history must hold what the caller actually heard.
TRANSFER_FAILED_LINE = (
    "Sorry about that, it looks like no one is available. How can I help you instead?"
)
# Spoken when the <Dial> could not even be started. No clip exists for it,
# so it is synthesised.
TRANSFER_NOT_STARTED_LINE = (
    "Sorry, I couldn't get through to the team just now. I've passed your "
    "details on and someone will call you back."
)
# Hidden from the caller, read by the model. Without it the model sees only
# "I'll transfer you now" in history and offers the transfer again.
TRANSFER_FAILED_NOTE = (
    "The transfer to staff just failed — nobody could be reached — so the "
    "caller is still with you. A callback request with their number has already been "
    "passed to staff. Do not offer another transfer unless they ask for a "
    "person again; help them directly, and if they ask, tell them someone will "
    "call them back."
)

# Fire-and-forget tasks need a strong reference or the loop may collect them
# mid-flight (asyncio keeps only weak references to tasks).
_in_flight: set = set()


async def notify_failed_transfer(
    caller_phone: str,
    tenant_id: str,
    call_sid: str,
    reason: str,
) -> None:
    """
    Tell staff a caller could not be put through and wants a call back.

    The full number goes into the notification — staff have to dial it — and
    only the masked one into logs.
    """
    when = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%d %b %H:%M")
    detail = (
        f"Caller tried to reach staff at {when} but the transfer failed ({reason}). "
        f"Please call them back. CallSid: {call_sid or 'unknown'}"
    )
    logger.info(
        "📞 Failed transfer (%s) for %s — recording callback request",
        reason, mask_phone(caller_phone),
    )

    # 1. Durable record + email. Separate try blocks: either channel alone is
    #    enough for staff to act, so one failing must not suppress the other.
    try:
        from services.staff_notifications import staff_notification_service
        await staff_notification_service.notify_new_callback_request(
            customer_phone=caller_phone or "unknown",
            customer_name="Caller (transfer not answered)",
            reason=detail,
            urgency="high",
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.error("🔴 Failed-transfer callback record failed for %s: %s",
                     mask_phone(caller_phone), e)

    # 2. SMS to the staff phone — the one channel someone sees within minutes.
    if settings.STAFF_PHONE_NUMBER:
        try:
            from services.sms import sms_service
            await sms_service.send_sms(
                to_number=settings.STAFF_PHONE_NUMBER,
                message=f"📞 MISSED TRANSFER ({reason}) {when}: please call back {caller_phone or 'unknown number'}",
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error("🔴 Failed-transfer staff SMS failed for %s: %s",
                         mask_phone(caller_phone), e)


def schedule_failed_transfer_notification(**kwargs) -> asyncio.Task:
    """Run `notify_failed_transfer` beside the call without waiting on it."""
    task = asyncio.create_task(notify_failed_transfer(**kwargs))
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)
    return task
