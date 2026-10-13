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
    # --- found in review: narration and deferral are not asks ----------------
    # Each of these was read as an ask and would have handed a caller who had
    # just declined over to a person.
    ("No thanks, I'll speak to reception when I check in", REFUSE),
    ("nah I'll talk to someone when I get there", REFUSE),
    ("no it's fine, I was talking to the manager this morning", REFUSE),
    ("please don't, I'll speak to someone tomorrow", REFUSE),
    ("my mate was talking to the owner last week", NEITHER),
    ("transfer me later", NEITHER),
    ("why would you transfer me", NEITHER),
    ("should I speak to the manager about that", NEITHER),
    # --- found in review: a possessive is not a person -----------------------
    ("I'd like the owner's phone number", NEITHER),
    ("I need the manager's email address", NEITHER),
    ("I need the manager’s email address", NEITHER),
    # --- found in review: "can/could I not" is a polite ask (AU/UK) ----------
    ("Can I not just speak to someone", ASK),
    ("Could I not speak to the manager", ASK),
    ("can you not transfer me", REFUSE),
    # --- found in review: other gaps ----------------------------------------
    ("I can't talk to a person right now", REFUSE),
    ("I don't want to be transferred", REFUSE),
    ("I never asked to be transferred", REFUSE),
    ("agent", ASK),
    ("representative", ASK),
    ("a real person please", ASK),
    ("transfer please", ASK),
    ("I'd like to talk to whoever's at the desk", ASK),
    ("put me threw to reception", ASK),
    # --- how Australian callers ask ------------------------------------------
    ("Can you put me through to reception, mate?", ASK),
    ("Can I have a word with the manager?", ASK),
    ("Can I get onto someone at the front desk?", ASK),
    ("I wouldn't mind talking to a real person.", ASK),
    ("Can't I just speak to someone?", ASK),
    ("Why won't you put me through?", ASK),
    ("Sorry, could I speak to whoever's on the desk?", ASK),
    ("Honestly mate, I just want a real person.", ASK),
    ("Yeah nah, can you put me through to someone?", ASK),
    ("I've had enough of this, put me through to a human.", ASK),
    ("Any chance I could speak to the manager?", ASK),
    ("I need to speak to someone about a refund.", ASK),
    ("I was hoping to speak to the manager.", ASK),
    ("I'll be there Friday but can I talk to reception now?", ASK),
    # --- how Australian callers decline --------------------------------------
    ("Nah, I'm right thanks.", REFUSE),
    ("Nah you're right, don't worry about it.", REFUSE),
    ("No, don't bother putting me through.", REFUSE),
    ("Not right now thanks, I'll call back.", REFUSE),
    ("I'm good thanks, I'll sort it out myself.", REFUSE),
    ("Don't put me through to anyone, I just want to book a room.", REFUSE),
    ("No I don't need to speak to anyone, I'm all sorted.", REFUSE),
    ("Leave it, I'll talk to the manager when I check in.", REFUSE),
    ("Nah I'll ring reception tomorrow.", REFUSE),
    ("I won't be talking to anyone, just book it.", REFUSE),
    # --- neither: talking about staff, not asking for them -------------------
    ("I'll just talk to reception when I get there, thanks.", NEITHER),
    ("I spoke to the manager yesterday about my booking.", NEITHER),
    ("The owner said I could get a late checkout.", NEITHER),
    ("What's the manager's name?", NEITHER),
    ("Do I need to talk to reception to get a key?", NEITHER),
    ("I was speaking to someone earlier and they said it was booked.", NEITHER),
    ("When I get there, should I talk to the front desk?", NEITHER),
    ("Can I speak to someone tomorrow morning about the invoice?", NEITHER),
    ("Could you pass on a message to the manager?", NEITHER),
    ("I'll have a word with the manager when I get in.", NEITHER),
    ("I've already spoken to someone at the front desk.", NEITHER),
    ("Maybe I'll talk to the owner next time I'm in.", NEITHER),
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


@pytest.mark.parametrize("declined", [
    "No thanks, I'll speak to reception when I check in",
    "nah I'll talk to someone when I get there",
    "no it's fine, I was talking to the manager this morning",
    "please don't, I'll speak to someone tomorrow",
])
def test_declining_an_offer_while_mentioning_staff_is_not_consent(declined):
    """
    The review's consent violation: the agent offered a transfer, the caller
    said no and mentioned staff they would see later, and the gate read the
    staff-mention as an ask.
    """
    history = [
        {"role": "assistant", "content": "Want me to put you through to reception?"},
        {"role": "user", "content": declined},
    ]
    assert not transfer_consent_given(history), declined
    assert transfer_refused(declined), declined


def test_a_curly_apostrophe_from_the_transcriber_still_negates():
    assert transfer_intent("I don’t want to speak to anyone") == REFUSE


def test_the_table_is_big_enough_to_mean_something():
    assert len(UTTERANCES) >= 80
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
