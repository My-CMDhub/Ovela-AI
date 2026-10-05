"""
Did the caller ask for a person, turn one down, or neither?

Two gates read the same sentence: the orchestrator's consent gate
(`transfer_consent_given`) and the dispatcher's guard in `transfer_to_staff`
(`transfer_refused`). They used to read it differently — the gate matched
"get me" / "speak to" on their own, the guard refused anything containing
"no" or "don't" — so "No, I want to speak to a person" was waved through by
one and refused by the other and the model looped, unable to transfer, while
"get me a room for Friday" counted as asking for a human.

Each row is something a caller could plausibly say, and what it means.
"""

import pytest

from services.voice_agent.text_utils import (
    transfer_consent_given,
    transfer_intent,
    transfer_refused,
)

ASK, REFUSE, NEITHER = "ask", "refuse", None

UTTERANCES = [
    # --- plain asks ---------------------------------------------------------
    ("Can I speak to someone please?", ASK),
    ("Put me through to the front desk.", ASK),
    ("I'd like to talk to a manager.", ASK),
    ("Can you transfer me to reception?", ASK),
    ("Get me a human.", ASK),
    ("Could you get me someone from the front desk", ASK),
    ("Reception, please.", ASK),
    ("I need a real person", ASK),
    ("connect me with staff please", ASK),
    ("Is there someone I can talk to?", ASK),
    # --- asks that open with a "no" or a complaint about the agent -----------
    ("No, I want to speak to a person.", ASK),
    ("no I want to speak to a person", ASK),
    ("I don't want the robot, put me through.", ASK),
    ("I don't want the robot put me through", ASK),
    ("Nah, just get me the manager.", ASK),
    ("Are you a robot? Put me through to someone.", ASK),
    ("I don't know, can I talk to somebody at reception?", ASK),
    # --- refusals of the transfer itself ------------------------------------
    ("No, don't transfer me.", REFUSE),
    ("no don't transfer me", REFUSE),
    ("I don't want to speak to anyone.", REFUSE),
    ("Please don't put me through, I'll sort it out with you.", REFUSE),
    ("I do not need to talk to a person.", REFUSE),
    ("No thanks.", REFUSE),
    ("No need to transfer me, you've been helpful.", REFUSE),
    ("Can I speak to someone about parking? Actually no, just tell me.", REFUSE),
    ("can I speak to someone about parking actually no just tell me", REFUSE),
    ("Put me through to reception. Oh never mind, I found it.", REFUSE),
    ("I'd rather not speak to a human.", REFUSE),
    # --- neither: "get me" / "speak to" without a person after them ---------
    ("Get me a room for Friday.", NEITHER),
    ("Can you get me the price for two nights?", NEITHER),
    ("I want to speak to the booking, I mean change the booking.", NEITHER),
    ("Am I talking to a real person?", NEITHER),
    ("Is the front desk open late?", NEITHER),
    ("Actually, I am calling for Sarah.", NEITHER),
    ("Yes, no problem.", NEITHER),
    ("I'd like to talk to you about a booking.", NEITHER),
]


@pytest.mark.parametrize("utterance,expected", UTTERANCES)
def test_what_the_caller_meant(utterance, expected):
    assert transfer_intent(utterance) == expected, utterance


@pytest.mark.parametrize("utterance,expected", UTTERANCES)
def test_the_consent_gate_and_the_dispatcher_guard_agree(utterance, expected):
    """
    The orchestrator lets a transfer through only on consent; the dispatcher
    refuses it only on a refusal. For one sentence they must never both say
    "go" and "stop" — that is how the loop happened.
    """
    history = [{"role": "user", "content": utterance}]
    consent = transfer_consent_given(history)
    refused = transfer_refused(utterance)
    assert consent == (expected == ASK), utterance
    assert refused == (expected == REFUSE), utterance
    assert not (consent and refused), utterance


def test_a_yes_to_an_offer_is_still_consent():
    history = [
        {"role": "assistant", "content": "Want me to put you through to reception?"},
        {"role": "user", "content": "Yes please."},
    ]
    assert transfer_consent_given(history)
    assert not transfer_refused("Yes please.")


def test_a_yes_that_takes_it_back_is_not_consent():
    history = [
        {"role": "assistant", "content": "Want me to put you through to reception?"},
        {"role": "user", "content": "Yes, actually no, don't transfer me."},
    ]
    assert not transfer_consent_given(history)


def test_a_curly_apostrophe_from_the_transcriber_still_negates():
    assert transfer_intent("I don’t want to speak to anyone") == REFUSE


def test_the_table_is_big_enough_to_mean_something():
    assert len(UTTERANCES) >= 25
    assert {e for _, e in UTTERANCES} == {ASK, REFUSE, NEITHER}


def _dispatcher():
    from unittest.mock import AsyncMock, MagicMock
    from services.voice_agent.functions.coalcreek_handlers import CoalCreekFunctionDispatcher

    return CoalCreekFunctionDispatcher(
        db_service=MagicMock(), user_phone="+61400000000",
        save_reservation_fn=AsyncMock(), abuse_protection=MagicMock(),
    )


@pytest.mark.asyncio
async def test_the_dispatcher_transfers_a_caller_who_said_no_then_asked():
    """The live failure: the guard refused this and the model looped."""
    dispatcher = _dispatcher()
    result = await dispatcher.execute(
        "transfer_to_staff", {"_user_utterance": "No, I want to speak to a person."}
    )
    assert result.get("action") == "transfer", result


@pytest.mark.asyncio
async def test_the_dispatcher_still_refuses_a_caller_who_said_dont():
    dispatcher = _dispatcher()
    result = await dispatcher.execute(
        "transfer_to_staff", {"_user_utterance": "No, don't transfer me."}
    )
    assert result.get("success") is False
    assert result.get("action") != "transfer"
