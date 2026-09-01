"""
tests/test_tool_preconditions.py — what must be true before a one-way tool runs.

`transfer_to_staff` is the reference: the prompt already forbade dialling
without a yes, and the model broke that rule on a live call, so the rule moved
into code where it cannot decay. These are the same shape, for the tools that
spend money or change a booking. All Track A: deterministic, no model.

Two of them were open holes rather than weak ones.

  resend_payment_link took `user_phone` as an argument and never read it, so
  naming any guest's email address re-sent a Stripe checkout against their
  booking and returned its reference and payment status.

  resend_payment_confirmation ran its payment-status guard ahead of its
  ownership check and refused with "payment_status='pending'" — which answers
  the question a stranger was really asking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.voice_agent.functions.coalcreek_handlers import (
    caller_owns,
    handle_resend_payment_confirmation,
    handle_resend_payment_link,
)

CALLER = "+61499888777"
STRANGER_BOOKING = {
    "booking_reference": "CC-12345", "guest_name": "Bob Smith",
    "guest_phone": "+61411222333", "guest_email": "bob@example.com",
    "room_type": "queen", "check_in_date": "2026-10-01",
    "check_out_date": "2026-10-03", "total_amount": 300,
    "status": "pending_payment", "payment_status": "pending",
}


class TestCallerOwns:
    def test_the_same_number_written_two_ways_is_one_number(self):
        assert caller_owns({"guest_phone": "+61499888777"}, "0499888777")
        assert caller_owns({"guest_phone": "0499 888 777"}, "+61499888777")

    def test_a_different_number_is_not_a_match(self):
        assert not caller_owns(STRANGER_BOOKING, CALLER)

    def test_no_caller_id_is_a_no(self):
        """Withheld caller ID reads as "we cannot tell", and there is no reading
        of that which should end in acting on somebody's money."""
        assert not caller_owns({"guest_phone": "+61499888777"}, "")

    def test_a_booking_with_no_number_on_it_is_a_no(self):
        assert not caller_owns({"guest_phone": ""}, CALLER)


class TestResendPaymentLink:
    @pytest.mark.asyncio
    async def test_a_stranger_gets_no_link_and_no_status(self):
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[STRANGER_BOOKING])

        result = await handle_resend_payment_link(
            {"guest_email": "bob@example.com"}, db, CALLER)

        assert result["success"] is False
        assert result.get("privacy_refusal") is True
        # Not the reference, not the name, and not whether they have paid.
        assert "CC-12345" not in str(result)
        assert "Bob Smith" not in str(result)
        assert "pending" not in result["message"].lower()

    @pytest.mark.asyncio
    async def test_the_refusal_offers_a_way_forward(self):
        """A guest ringing from their partner's phone is a real caller, not an
        attacker. A refusal that dead-ends them is its own kind of failure."""
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[STRANGER_BOOKING])

        result = await handle_resend_payment_link(
            {"guest_email": "bob@example.com"}, db, CALLER)

        assert "reception" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_the_callers_own_booking_gets_past_the_gate(self):
        """A booking already paid is refused for a different reason entirely —
        which proves the ownership check let it through rather than swallowing
        every request."""
        mine = dict(STRANGER_BOOKING, guest_phone=CALLER,
                    status="paid", payment_status="paid")
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[mine])

        result = await handle_resend_payment_link(
            {"guest_email": "bob@example.com"}, db, CALLER)

        assert result.get("privacy_refusal") is None
        assert result.get("already_paid") is True


class TestResendPaymentConfirmation:
    @pytest.mark.asyncio
    async def test_ownership_is_checked_before_payment_status_is_disclosed(self):
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[STRANGER_BOOKING])

        result = await handle_resend_payment_confirmation(
            {"guest_email": "bob@example.com"}, db, CALLER)

        assert result["success"] is False
        assert result.get("privacy_refusal") is True
        # The old ordering refused with the payment status in the error string.
        assert "payment_status" not in str(result)
        assert "pending" not in str(result).lower()


class TestUpdateGuestInfoNeedsIdentity:
    """The handler locks this to the caller's own number, which keeps it away
    from a stranger's booking. It does not establish that the guest is the one
    holding the handset — and this tool patches the reservation and re-sends
    the payment link to whatever email it is handed. So the gate lives with the
    other identity-dependent gates, in the orchestrator."""

    @pytest.fixture
    def agent(self):
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"success": True})
        return agent

    @pytest.mark.asyncio
    async def test_refused_while_a_reservation_exists_and_nobody_has_identified(self, agent):
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[STRANGER_BOOKING])

        result = await agent._execute_tool("update_guest_info", {"guest_email": "x@y.com"}, [])

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()
        # The refusal has to say what to do instead, or the model just retries.
        assert "lookup_booking" in result["message"]

    @pytest.mark.asyncio
    async def test_allowed_once_a_tool_has_confirmed_who_is_calling(self, agent):
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[STRANGER_BOOKING])
        agent.call_state.identity_confirmed = True

        result = await agent._execute_tool("update_guest_info", {"guest_email": "x@y.com"}, [])

        assert result["success"] is True
        agent.dispatcher.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_allowed_when_there_is_no_reservation_to_change(self, agent):
        """A new caller giving their details for a booking they are about to
        make has nothing to protect. Closing the gate here would break the
        ordinary path to buy nothing."""
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[])

        result = await agent._execute_tool("update_guest_info", {"guest_name": "Ada"}, [])

        assert result["success"] is True
        agent.dispatcher.execute.assert_called_once()


class TestOneEmailTwoStays:
    """One address can carry two bookings — a guest who also booked a room for
    a friend. Refusing the whole request because one of them is not theirs
    would dead-end a legitimate caller, so the caller's own are kept and the
    rest are simply not there."""

    @pytest.mark.asyncio
    async def test_the_callers_own_stay_is_still_reachable(self):
        mine = dict(STRANGER_BOOKING, booking_reference="CC-99999",
                    guest_phone=CALLER, status="paid", payment_status="paid")
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[STRANGER_BOOKING, mine])

        result = await handle_resend_payment_link(
            {"guest_email": "bob@example.com"}, db, CALLER)

        assert result.get("privacy_refusal") is None
        assert result.get("booking_reference") == "CC-99999"
        assert "CC-12345" not in str(result)      # the other stay stays invisible


class TestBookingNeedsARealSummary:
    """
    create_booking_request holds a room, queues an email and raises a Stripe
    checkout. Its own gate is `has_user_confirmed_summary` — an argument the
    model fills in, so the gate asks the model whether the model did the thing.

    Measured over ten replays of two booking scenarios: 4 of 7 attempts asserted
    YES with no price-and-date summary in the transcript. The clearest one is
    the second test below, taken verbatim from a replay.
    """

    @pytest.fixture
    def agent(self):
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"success": True})
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[])
        return agent

    CONFIRMED_YES = {"guest_name": "Ada Lovelace", "has_user_confirmed_summary": "YES"}

    @pytest.mark.asyncio
    async def test_the_models_own_word_is_not_enough(self, agent):
        """An empty transcript and has_user_confirmed_summary=YES. Nothing was
        read back to anybody, and the argument saying otherwise is the model's."""
        result = await agent._execute_tool("create_booking_request", self.CONFIRMED_YES, [])

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_yes_about_the_email_address_is_not_a_confirmed_booking(self, agent):
        """Verbatim from a replay. The caller agreed that their email was spelled
        correctly. The model turned that into a confirmed booking summary."""
        history = [
            {"role": "assistant",
             "content": "Got it — that's ada at example dot com, right? Would you "
                        "like to confirm and proceed with the booking?"},
            {"role": "user", "content": "Yes, that's all correct, please go ahead."},
        ]

        result = await agent._execute_tool("create_booking_request", self.CONFIRMED_YES, history)

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()
        # The refusal has to be actionable or the model simply tries again.
        assert "read the booking summary back" in result["error"]

    @pytest.mark.asyncio
    async def test_a_real_read_back_and_a_real_yes_goes_through(self, agent):
        """Also verbatim. The gate has to let the ordinary path work, or it has
        traded a rare wrong booking for a call that can never book at all."""
        history = [
            {"role": "assistant",
             "content": "The Double Room is available from September 10th for two "
                        "nights at $135 per night. Would you like me to place a hold "
                        "and send the payment link?"},
            {"role": "user", "content": "Yes, that's all correct, please go ahead."},
        ]

        result = await agent._execute_tool("create_booking_request", self.CONFIRMED_YES, history)

        assert result["success"] is True
        agent.dispatcher.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_summary_the_caller_never_answered_is_not_agreement(self, agent):
        history = [
            {"role": "assistant",
             "content": "Ada, the 10th of September, Double Room at $135 per night."},
            {"role": "user", "content": "And what time is check-in?"},
        ]

        result = await agent._execute_tool("create_booking_request", self.CONFIRMED_YES, history)

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()


class TestUpdateGuestInfoTellsTheTruth:
    """
    It used to answer "Details safely stored in my temporary memory for this
    call" for a caller with no reservation — zero DB writes, no in-memory
    store, nothing. The model repeated the claim to the caller. A tool that
    reports an action it did not perform is the same bug class as a tool that
    returns an action nobody performs.
    """

    @pytest.mark.asyncio
    async def test_it_does_not_claim_to_have_saved_what_it_did_not_save(self):
        from services.voice_agent.functions.coalcreek_handlers import handle_update_guest_info
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[])   # a new caller

        result = await handle_update_guest_info(
            {"guest_name": "Ada Lovelace", "guest_email": "ada@example.com"}, db, CALLER)

        assert result["stored"] is False
        assert "stored" not in result["message"].lower()
        assert "nothing is saved" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_a_real_update_still_reports_as_one(self):
        from services.voice_agent.functions.coalcreek_handlers import handle_update_guest_info
        mine = dict(STRANGER_BOOKING, guest_phone=CALLER, guest_email="",
                    status="pending_payment", payment_status="pending")
        db = MagicMock()
        db.lookup_motel_reservation = AsyncMock(return_value=[dict(mine, **{"$id": "doc1"})])
        db.update_motel_reservation = AsyncMock()

        result = await handle_update_guest_info({"guest_name": "Bob Smith"}, db, CALLER)

        assert result["stored"] is True
        db.update_motel_reservation.assert_awaited_once()


class TestTheCallerIsHeardBeforeAnyGate:
    """A refusal is not a reason to forget the name the caller just spelled
    out. The details are recorded before the gates run, or a blocked tool
    silently throws away the only copy."""

    @pytest.mark.asyncio
    async def test_a_refused_booking_still_keeps_what_the_caller_said(self):
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"success": True})
        agent.dispatcher.caller_reservation = AsyncMock(return_value=[])

        # No summary was read back, so this is refused by the booking gate.
        result = await agent._execute_tool(
            "create_booking_request",
            {"guest_name": "Siobhan O'Connor", "guest_email": "s.oconnor@bigpond.com",
             "has_user_confirmed_summary": "YES"}, [])

        assert result["success"] is False
        agent.dispatcher.execute.assert_not_called()
        assert agent.call_state.heard_name == "Siobhan O'Connor"
        assert agent.call_state.heard_email == "s.oconnor@bigpond.com"


class TestTheAvailabilityMemoReachesTheHandler:
    """The per-call availability cache only ever worked on the legacy handler,
    which passes a context. The cascaded path called execute() with two
    arguments, so `context` was None and every check_availability re-ran the
    whole query — two or three times in one booking conversation."""

    @pytest.mark.asyncio
    async def test_a_per_call_context_is_threaded_through(self):
        from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
        agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock())
        agent.dispatcher = MagicMock()
        agent.dispatcher.execute = AsyncMock(return_value={"available": True})

        await agent._execute_tool("check_availability", {"room_type": "queen"}, [])

        context = agent.dispatcher.execute.await_args.args[2]
        assert isinstance(context.get("availability_cache"), dict)
