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
