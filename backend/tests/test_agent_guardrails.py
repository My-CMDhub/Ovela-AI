"""
Guards on what the agent does, as opposed to what it knows.

Both of these come from one real call — CallSid CAe887d2f3a6bda15e95cc549a97220a78,
31 August, on v419 — where the caller's name could not be found and the agent
then dialled a human without being asked to.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.voice_agent.text_utils import transfer_consent_given


# --- a failed lookup must offer a way forward, not an exit -------------------

@pytest.mark.asyncio
async def test_a_failed_lookup_asks_the_caller_to_spell_rather_than_offering_reception():
    """
    The "nothing found" result used to read: "I couldn't find a booking ... want
    me to put you through to reception?" The tool was scripting the escalation,
    so the agent proposed a transfer on the caller's first miss and had nothing
    else to try. Spelling the name out already resolves it — the caller was
    simply never asked.
    """
    from services.voice_agent.functions.coalcreek_handlers import handle_lookup_booking

    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[])

    result = await handle_lookup_booking({"guest_name": "Drew Patel"}, db, "+61400000123")

    assert result.get("found") is False
    message = result.get("message", "").lower()
    assert "spell" in message, "the caller is never offered the one thing that works"
    for exit_word in ("reception", "front desk", "transfer", "put you through"):
        assert exit_word not in message, f"the tool proposes an exit ({exit_word!r})"


# --- transferring a call is not something to do on a hunch -------------------

def test_consent_is_given_by_saying_yes_to_an_offer():
    history = [
        {"role": "assistant", "content": "Want me to put you through to reception?"},
        {"role": "user", "content": "Yes please."},
    ]
    assert transfer_consent_given(history)


def test_consent_is_given_by_asking_for_a_person_outright():
    for asked in ("Can I speak to someone please?",
                  "Put me through to the front desk.",
                  "I'd like to talk to a manager."):
        assert transfer_consent_given([{"role": "user", "content": asked}]), asked


def test_a_yes_to_something_else_is_not_consent_to_transfer():
    history = [
        {"role": "assistant", "content": "Would you like me to check those dates?"},
        {"role": "user", "content": "Yes please."},
    ]
    assert not transfer_consent_given(history)


def test_the_turn_from_the_real_call_is_not_consent():
    """What the caller actually said before the agent dialled a human."""
    history = [
        {"role": "assistant", "content": "I couldn't find a booking under that name."},
        {"role": "user", "content": "Actually, I am calling for Sarah."},
    ]
    assert not transfer_consent_given(history)


def test_silence_is_not_consent():
    assert not transfer_consent_given([])
    assert not transfer_consent_given([{"role": "user", "content": ""}])


@pytest.mark.asyncio
async def test_the_orchestrator_refuses_a_transfer_nobody_agreed_to():
    """
    The prompt already says to dial only on an explicit yes, and the model broke
    that rule on a live call. Handing a caller to a person ends what the agent
    can do for them, so the rule is enforced where it cannot be talked out of.
    """
    from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

    orch = CascadedPipelineOrchestrator(twilio_ws=MagicMock())
    orch.dispatcher = MagicMock()
    orch.dispatcher.execute = AsyncMock(return_value={"success": True})
    orch.history = [
        {"role": "assistant", "content": "I couldn't find a booking under that name."},
        {"role": "user", "content": "Actually, I am calling for Sarah."},
    ]

    result = await orch._execute_tool("transfer_to_staff", {})

    orch.dispatcher.execute.assert_not_awaited()
    assert result.get("success") is False
    assert "ask" in result.get("message", "").lower()


@pytest.mark.asyncio
async def test_the_orchestrator_allows_a_transfer_the_caller_asked_for():
    from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

    orch = CascadedPipelineOrchestrator(twilio_ws=MagicMock())
    orch.dispatcher = MagicMock()
    orch.dispatcher.execute = AsyncMock(return_value={"success": True})
    orch.history = [{"role": "user", "content": "Can you put me through to reception?"}]

    result = await orch._execute_tool("transfer_to_staff", {})

    orch.dispatcher.execute.assert_awaited_once()
    assert result.get("success") is True
