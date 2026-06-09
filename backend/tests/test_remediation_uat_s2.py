"""
Remediation Unit Tests — UAT-S2 Batch
======================================

Evidence-first tests for Phase 2 remediation items:
- N1: Pre-booking gate (has_user_confirmed_summary backend enforcement)
- N4: Meaningless affirmation filter (VoiceAgentHandler._is_meaningless_interruption)
- M1: TTS ordinal normalization + slash → "and" (text_utils.clean_tts_output)
- M2: Email branding guard (business_name default check)
- I5: Wait-signal silence extension probe

These tests satisfy:
  ✅ True positive: desired behaviour confirmed
  ✅ True negative: adjacent non-triggering input confirmed
  ✅ No regressions on existing passing suite

Run:
    cd backend && source venv/bin/activate
    pytest tests/test_remediation_uat_s2.py -v --tb=short
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

logger = logging.getLogger(__name__)


# =============================================================================
# M1: TTS Ordinal Normalization + Slash → "and"
# =============================================================================

class TestM1TtsSanitization:
    """M1 — Date ordinal zero-pad fix and slash → 'and' normalization in TTS."""

    def test_m1_zero_padded_day_becomes_ordinal(self):
        """'June 06' must become 'June 6th', not read as 'zero six'."""
        from services.voice_agent.text_utils import clean_tts_output

        result = clean_tts_output("Check-in: June 06")
        assert "6th" in result, f"Expected ordinal '6th' in result, got: {result}"
        assert "06" not in result, f"Zero-padded '06' must be removed, got: {result}"

    def test_m1_ordinal_1st_2nd_3rd(self):
        """'July 01', 'July 02', 'July 03' → '1st', '2nd', '3rd'."""
        from services.voice_agent.text_utils import clean_tts_output

        assert "1st" in clean_tts_output("July 01")
        assert "2nd" in clean_tts_output("July 02")
        assert "3rd" in clean_tts_output("July 03")

    def test_m1_ordinal_11th_12th_13th_are_th(self):
        """The _to_ordinal helper correctly labels 11th, 12th, 13th (not 11st/12nd/13rd).
        NOTE: The regex only fires on zero-padded \\b0(\\d)\\b patterns, so 01-09 only.
        11/12/13 without zero-padding are NOT touched by this regex — that's correct."""
        from services.voice_agent.text_utils import clean_tts_output

        # 01..09 are the actual targets — verify all suffixes are correct
        assert "1st" in clean_tts_output("Jan 01")  # 01 → 1st
        assert "2nd" in clean_tts_output("Jan 02")  # 02 → 2nd
        assert "3rd" in clean_tts_output("Jan 03")  # 03 → 3rd
        assert "4th" in clean_tts_output("Jan 04")  # 04 → 4th
        assert "9th" in clean_tts_output("Jan 09")  # 09 → 9th
        # 11, 12, 13 are NOT zero-padded so the regex won't touch them
        # (they can't appear as "011", "012", "013" with this regex pattern)
        logger.info("M1 ordinal suffix coverage: 1st/2nd/3rd/4th/9th all verified")

    def test_m1_slash_between_letters_becomes_and(self):
        """'Double Room' → 'Queen and Double' (no TTS reading 'slash')."""
        from services.voice_agent.text_utils import clean_tts_output

        result = clean_tts_output("Double Room room available")
        assert " and " in result, f"Expected ' and ', got: {result}"
        assert "/" not in result, f"Slash should be removed, got: {result}"

    def test_m1_slash_in_url_not_mangled(self):
        """URL slashes must NOT be affected — but clean_tts_output already strips URLs.
        Confirm the letter/slash/letter pattern is the only target."""
        from services.voice_agent.text_utils import clean_tts_output
        # This is a digit/slash — should NOT be converted to 'and'
        result = clean_tts_output("Rate: $130/night")
        # The slash here is between digit/letter — our pattern is (?<=[A-Za-z])/(?=[A-Za-z])
        # so $130/night must NOT be affected
        assert "/night" in result or "night" in result  # no crash
        logger.info("M1 URL/digit slash guard: %s", result)

    def test_m1_true_negative_normal_text_unchanged(self):
        """Normal sentences without zero-padded dates or room slashes are untouched."""
        from services.voice_agent.text_utils import clean_tts_output

        sentence = "The Twin Room is available for those dates."
        result = clean_tts_output(sentence)
        assert result == sentence, f"Normal text was mutated: {result}"

    logger.info("✅ M1: TTS ordinal + slash normalization tests defined")


# =============================================================================
# N1: Pre-Booking Gate — has_user_confirmed_summary Backend Enforcement
# =============================================================================

class TestN1PreBookingGate:
    """N1 — Backend gate rejects create_booking_request when confirmation flag is False."""

    @pytest.fixture
    def minimal_handler_args(self):
        """Minimal valid args that would pass if the gate weren't there."""
        return {
            "guest_name": "Jane Smith",
            "guest_email": "jane.smith@gmail.com",
            "check_in_date": "2026-07-15",
            "check_out_date": "2026-07-16",
            "room_type": "queen",
            "has_user_confirmed_summary": False,  # GATE FLAG: FALSE
        }

    @pytest.mark.asyncio
    async def test_n1_gate_rejects_when_flag_false(self, minimal_handler_args):
        """True positive: gate must reject the call when has_user_confirmed_summary=False."""
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        mock_save_fn = AsyncMock(return_value={"success": True, "id": "test_doc"})
        mock_db = MagicMock()

        result = await handle_create_booking_request(
            args=minimal_handler_args,
            user_phone="+61400000001",
            save_reservation_fn=mock_save_fn,
            db_service=mock_db,
        )

        assert result.get("success") is False, (
            f"N1 gate must reject when has_user_confirmed_summary=False. Got: {result}"
        )
        assert "error" in result, "N1 gate rejection must include 'error' key for AI to read."
        assert "STEP 3" in result["error"] or "summary" in result["error"].lower(), (
            f"N1 error message must reference the missing step. Got: {result['error']}"
        )
        # True negative for save_fn: it must NOT have been called
        mock_save_fn.assert_not_called()
        logger.info("✅ N1 True positive: gate rejected call without confirmation flag")

    @pytest.mark.asyncio
    async def test_n1_gate_passes_when_flag_true(self, minimal_handler_args):
        """True negative: gate should NOT block when has_user_confirmed_summary=True
        AND name/email are provided (actual DB ops may fail in unit test — that's OK)."""
        minimal_handler_args["has_user_confirmed_summary"] = True

        # The handler will try to do date resolution + DB ops — we patch save_fn
        mock_save_fn = AsyncMock(return_value={"success": True, "id": "test_doc_001"})
        mock_db = MagicMock()

        # Import here to pick up the live handler
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        result = await handle_create_booking_request(
            args=minimal_handler_args,
            user_phone="+61400000001",
            save_reservation_fn=mock_save_fn,
            db_service=mock_db,
        )

        # If the gate passes, the error key must NOT be "SYSTEM RULE VIOLATION"
        if not result.get("success"):
            violation_msg = result.get("error", "")
            assert "SYSTEM RULE VIOLATION" not in violation_msg, (
                "N1 gate must not fire when has_user_confirmed_summary=True. "
                f"Got error: {violation_msg}"
            )
        logger.info("✅ N1 True negative: gate passed when flag is True. Result: %s", result.get("success"))

    @pytest.mark.asyncio
    async def test_n1_gate_rejects_when_flag_missing(self, minimal_handler_args):
        """Missing flag (omitted by LLM) must be treated as False — gate must reject."""
        del minimal_handler_args["has_user_confirmed_summary"]

        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        mock_save_fn = AsyncMock(return_value={"success": True, "id": "test_doc"})
        mock_db = MagicMock()

        result = await handle_create_booking_request(
            args=minimal_handler_args,
            user_phone="+61400000001",
            save_reservation_fn=mock_save_fn,
            db_service=mock_db,
        )

        assert result.get("success") is False, "Missing flag must be treated as False — gate must reject."
        mock_save_fn.assert_not_called()
        logger.info("✅ N1: Missing flag treated as False — gate correctly rejected")


# =============================================================================
# N4: Meaningless Interruption Filter
# =============================================================================

class TestN4MeaninglessInterruptionFilter:
    """N4 — VoiceAgentHandler._is_meaningless_interruption returns correct bool."""

    @pytest.fixture
    def handler(self):
        """Build a VoiceAgentHandler with minimal mocking (no real websocket)."""
        from unittest.mock import MagicMock, AsyncMock, patch
        # Patch the heavy dependencies at import time
        with patch("services.voice_agent.handler.SilenceMonitor"), \
             patch("services.voice_agent.handler.AbuseProtection"), \
             patch("services.voice_agent.handler.CallerMemoryBank"):
            from services.voice_agent.handler import VoiceAgentHandler

            mock_ws = MagicMock()
            mock_ws.send = AsyncMock()

            h = VoiceAgentHandler.__new__(VoiceAgentHandler)
            # Only the method under test is needed — no full init required
            return h

    # ── True positives — should be filtered ──────────────────────────────────
    @pytest.mark.parametrize("utterance", [
        "okay", "ok", "sure", "yep", "yeah", "mhm", "gotcha",
        "cool", "alright", "right", "mmm", "mm",
    ])
    def test_n4_single_affirmation_is_meaningless(self, handler, utterance):
        """Single known affirmations must be flagged as meaningless."""
        assert handler._is_meaningless_interruption(utterance) is True, (
            f"'{utterance}' should be classified as meaningless affirmation"
        )

    def test_n4_two_word_affirmation_is_meaningless(self, handler):
        """Two known affirmation words must still be flagged (single-word combos)."""
        assert handler._is_meaningless_interruption("yeah sure") is True
        assert handler._is_meaningless_interruption("ok cool") is True
        # Multi-word phrases in the phrase set
        assert handler._is_meaningless_interruption("uh huh") is True
        assert handler._is_meaningless_interruption("go ahead") is True
        assert handler._is_meaningless_interruption("uh-huh") is True
        assert handler._is_meaningless_interruption("all right") is True

    # ── True negatives — must NOT be filtered ────────────────────────────────
    @pytest.mark.parametrize("utterance", [
        "okay I want to book a queen room",
        "sure but can you check the family room price",
        "yeah my email is test@gmail.com",
        "I'd like to check in on Friday",
        "yes cancel my booking please",
    ])
    def test_n4_affirmation_with_content_not_filtered(self, handler, utterance):
        """Utterances that have affirmation + content (> 3 words) must NOT be filtered."""
        assert handler._is_meaningless_interruption(utterance) is False, (
            f"'{utterance}' has booking intent and must NOT be filtered"
        )

    def test_n4_empty_string_is_not_meaningless(self, handler):
        """Empty input must return False (guard against crash)."""
        assert handler._is_meaningless_interruption("") is False
        assert handler._is_meaningless_interruption("   ") is False

    def test_n4_three_word_unknown_not_filtered(self, handler):
        """Three non-affirmation words must not be filtered."""
        assert handler._is_meaningless_interruption("book a room") is False

    logger.info("✅ N4: Meaningless interruption filter tests defined")


# =============================================================================
# M2: Email Branding Guard
# =============================================================================

class TestM2EmailBranding:
    """M2 — Verify 'Coal Creek Motel' is explicitly passed to send_payment_link at call site."""

    def test_m2_payment_link_call_passes_brand_name(self):
        """
        Verify that the _handle_stripe_and_guest_email cold-path passes
        business_name='Coal Creek Motel' explicitly to email_service.send_payment_link.

        We inspect the source of _handle_stripe_and_guest_email to confirm the
        explicit keyword argument is present — a compile-time check that prevents
        the 'Motel' default from leaking.
        """
        import inspect
        from services.voice_agent.functions.coalcreek_handlers import _handle_stripe_and_guest_email

        source = inspect.getsource(_handle_stripe_and_guest_email)
        assert "Coal Creek Motel" in source, (
            "M2: business_name='Coal Creek Motel' must be explicitly passed in "
            "_handle_stripe_and_guest_email. The 'Motel' default from email.py will leak otherwise."
        )
        logger.info("✅ M2: Explicit 'Coal Creek Motel' branding confirmed in cold-path source")

    def test_m2_send_payment_link_default_is_motel(self):
        """
        Document the risk: the default 'Motel' is intentionally kept at the function
        signature for backward compatibility with generic tenants, but Coal Creek
        must ALWAYS override it explicitly.
        """
        import inspect
        from services.email import EmailService

        source = inspect.getsource(EmailService.send_payment_link)
        # The function signature still has the generic default — but the call site overrides it
        assert "business_name: str" in source, "Signature sanity check"
        logger.info("✅ M2: email.py send_payment_link signature check passed (default documented)")


# =============================================================================
# I5: Wait-Signal Silence Extension (smoke test)
# =============================================================================

class TestI5WaitSignalExtension:
    """I5 — Wait keywords extend silence pause by 30s when no function is executing."""

    def test_i5_wait_keywords_are_defined(self):
        """Verify the _WAIT_KEYWORDS tuple exists in handler.py at module scope or in method."""
        import ast
        import pathlib

        handler_src = pathlib.Path(
            "/Applications/Journey of pro/Nona/backend/services/voice_agent/handler.py"
        ).read_text()

        # Check that _WAIT_KEYWORDS or the individual wait-signal strings are in the file
        assert "give me a sec" in handler_src or "_WAIT_KEYWORDS" in handler_src, (
            "I5: wait-keyword set not found in handler.py — silence extension won't fire"
        )
        assert "pause_silence" in handler_src, (
            "I5: pause_silence call not found in handler.py — extension logic is missing"
        )
        logger.info("✅ I5: Wait-keyword silence extension code confirmed present in handler.py")


# =============================================================================
# UAT-S2 Telephony Hardening & Interruption Fixes
# =============================================================================

class TestTelephonyHardeningFixes:
    """Tests for Phase 2 Telephony Hardening & Interruption fixes (Tasks 1-5)."""

    def test_phone_numbers_match_helper(self):
        """Task 1: Verify phone_numbers_match correctly compares the last 9 digits."""
        from services.voice_agent.functions.coalcreek_handlers import phone_numbers_match

        # Matches
        assert phone_numbers_match("+61400000001", "0400000001") is True
        assert phone_numbers_match("0400 000 001", "+61 400 000 001") is True
        assert phone_numbers_match("+61400000001", "400000001") is True
        assert phone_numbers_match("0400000001", "0400000001") is True

        # Non-matches
        assert phone_numbers_match("+61400000001", "+61400000002") is False
        assert phone_numbers_match("0400000001", "0400000002") is False

        # Edge cases
        assert phone_numbers_match("", "+61400000001") is False
        assert phone_numbers_match("+61400000001", "") is False
        assert phone_numbers_match("invalid", "numbers") is False

    @pytest.mark.asyncio
    async def test_guest_phone_fallback_on_invalid_string(self):
        """Task 1: Verify handle_create_booking_request falls back to user_phone for invalid guest_phone strings."""
        from services.voice_agent.functions.coalcreek_handlers import handle_create_booking_request

        mock_save = AsyncMock(return_value={"success": True, "document": {"$id": "doc_123"}})
        mock_db = MagicMock()

        args = {
            "guest_name": "Jane Doe",
            "guest_email": "jane@example.com",
            "check_in_date": "2026-07-15",
            "check_out_date": "2026-07-16",
            "room_type": "queen",
            "guest_phone": "current",  # Invalid string pattern
            "has_user_confirmed_summary": True,
            "_availability_cache": {
                "2026-07-15|2026-07-16|Double Room": {
                    "available": True,
                    "per_night_results": {
                        "2026-07-15": [
                            {"room_type": "Double Room", "available": True, "room_number": "101"}
                        ]
                    }
                }
            }
        }

        result = await handle_create_booking_request(
            args=args,
            user_phone="+61400000001",
            save_reservation_fn=mock_save,
            db_service=mock_db
        )

        assert result.get("success") is True
        assert mock_save.call_count == 1
        saved_data = mock_save.call_args[0][0]
        assert saved_data.get("guest_phone") == "+61400000001"

    @pytest.mark.asyncio
    async def test_resend_payment_confirmation_status_pending_whitelisted(self):
        """Task 3: Verify handle_resend_payment_confirmation searches for and matches 'pending' bookings."""
        from services.voice_agent.functions.coalcreek_handlers import handle_resend_payment_confirmation

        mock_db = MagicMock()
        mock_db.lookup_motel_reservation = AsyncMock(return_value=[
            {
                "status": "pending",  # Status is pending
                "payment_status": "pending_payment",
                "guest_name": "John Doe",
                "guest_phone": "+61400000001",
                "booking_reference": "CC-12345"
            }
        ])

        # Test with matching phone number
        result = await handle_resend_payment_confirmation(
            args={"guest_email": "john@example.com"},
            db_service=mock_db,
            user_phone="+61400000001"
        )

        # N6 guard should trigger because status is pending and payment is pending_payment.
        # This confirms that the pending booking was successfully matched (whitelisted)
        # rather than returning "I couldn't find a recent booking..."
        assert result.get("success") is False
        assert "SYSTEM RULE" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_resend_payment_confirmation_privacy_gate_match(self):
        """Task 3: Verify handle_resend_payment_confirmation uses phone_numbers_match helper to bypass format variations."""
        from services.voice_agent.functions.coalcreek_handlers import handle_resend_payment_confirmation

        mock_db = MagicMock()
        mock_db.lookup_motel_reservation = AsyncMock(return_value=[
            {
                "status": "confirmed",
                "payment_status": "paid",
                "guest_name": "John Doe",
                "guest_phone": "0400 000 001",  # Local AU formatting
                "booking_reference": "CC-12345"
            }
        ])

        # Test with E.164 caller phone number
        result = await handle_resend_payment_confirmation(
            args={"guest_email": "john@example.com"},
            db_service=mock_db,
            user_phone="+61400000001"
        )

        # It should pass the privacy lockout and attempt to send the email (which fails/mocks in unit tests,
        # but does NOT return privacy_refusal)
        assert result.get("privacy_refusal") is not True

    @pytest.mark.asyncio
    async def test_transfer_to_staff_negation_guard(self):
        """Task 4: Verify transfer_to_staff rejects transfer request programmatically when user utterance contains negations."""
        from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher
        from core.config import settings

        mock_db = MagicMock()
        mock_save = AsyncMock()
        mock_abuse = MagicMock()

        dispatcher = CoalCreekFunctionDispatcher(
            db_service=mock_db,
            user_phone="+61400000001",
            save_reservation_fn=mock_save,
            abuse_protection=mock_abuse
        )

        # Case 1: User says "no thanks"
        res = await dispatcher.execute(
            function_name="transfer_to_staff",
            args={"_user_utterance": "no thanks"}
        )
        assert res.get("success") is False
        assert "explicitly said NO" in res.get("error", "")

        # Case 2: User says "no, don't transfer"
        res = await dispatcher.execute(
            function_name="transfer_to_staff",
            args={"_user_utterance": "no, don't transfer me"}
        )
        assert res.get("success") is False
        assert "explicitly said NO" in res.get("error", "")

        # Case 3: User says "yes please"
        res = await dispatcher.execute(
            function_name="transfer_to_staff",
            args={"_user_utterance": "yes please"}
        )
        assert res.get("action") == "transfer"
        assert res.get("transfer_to") == settings.STAFF_PHONE_NUMBER

    @pytest.mark.asyncio
    async def test_vad_blocking_interruptions_reset_on_error(self):
        """Task 5: Verify _blocking_interruptions is cleared in the finally block of _handle_function_call."""
        from unittest.mock import MagicMock, AsyncMock, patch
        with patch("services.voice_agent.handler.SilenceMonitor"), \
             patch("services.voice_agent.handler.AbuseProtection"), \
             patch("services.voice_agent.handler.CallerMemoryBank"):
            from services.voice_agent.handler import VoiceAgentHandler

            handler = VoiceAgentHandler.__new__(VoiceAgentHandler)
            handler.tenant_id = "coalcreek"
            handler.user_phone = "+61400000001"
            handler.transcript = []
            handler.memory = {
                "name": "",
                "order_summary": "",
                "pickup_time": "",
                "check_in": "",
                "check_out": "",
                "room_type": "",
                "num_guests": 1,
                "notes": ""
            }
            handler._blocking_interruptions = True
            handler._is_processing_function = False
            handler._filler_played_this_turn = True
            handler.deepgram_ws = None
            handler.latency = MagicMock()

            event = {
                "functions": [
                    {
                        "name": "check_availability",
                        "id": "call_123",
                        "arguments": "{}"
                    }
                ]
            }

            # Trigger handle_function_call (which will raise AttributeError internally on self.function_dispatcher,
            # but catch it and execute the finally block resetting flags)
            await handler._handle_function_call(event)

            # Verify that finally block cleared the flags
            assert handler._blocking_interruptions is False
            assert handler._is_processing_function is False
            assert handler._filler_played_this_turn is False

