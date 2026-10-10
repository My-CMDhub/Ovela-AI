"""
tests/test_booking_moves.py — "Actually, can I move it to the weekend after?"

From the Kaggle probe dpquote/probe-move-a-paid-booking, which ran a copy of
this agent's prompt and tools against 6 models, 108 runs per kind of booking:

  paid, still ahead   good = no new hold, sent to reception     (one model: 3 of 18)
  paid, already over  good = says the stay is over, no new hold  (0 of 108, every model)
  unpaid              good = goes ahead with the change          (108 of 108)

The rule for paid bookings lived only in the prompt, nothing told the model a
stay was in the past, and create_booking_request accepted a new hold for any
of them. These tests pin the code-level rules that replace that:

  * every booking carries a change rule worked out from its dates and payment,
    and it reaches the model through lookup_booking and the call-state note
  * create_booking_request refuses to "move" a paid, in-house or finished stay
  * a caller with a live booking must say MOVE (replaces_booking_reference) or
    SECOND STAY (additional_stay) before a new hold is placed
  * moving an unpaid hold places the new one and cancels the old one
"""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.voice_agent.call_state import CallState
from services.voice_agent.functions import coalcreek_handlers as ch
from tests.test_booking_integrity import FakeMotelDb, _room

CALLER = "+61491570156"


def _d(n: int) -> str:
    return (ch._today_melbourne_date() + timedelta(days=n)).isoformat()


def _booking(ci, co, ref="CC-41273", status="confirmed", payment="paid", doc_id="old1"):
    return {"$id": doc_id, "booking_reference": ref, "guest_name": "Priya Nair",
            "guest_phone": CALLER, "guest_email": "priya.nair@example.com", "room_type": "queen",
            "check_in_date": ci, "check_out_date": co, "num_nights": 2, "status": status,
            "payment_status": payment, "total_amount": "320", "notes": ""}


PAID_AHEAD = _booking(_d(9), _d(11))
PAID_OVER = _booking(_d(-5), _d(-3))
UNPAID_AHEAD = _booking(_d(9), _d(11), status="pending", payment="pending_payment")
STAYING_NOW = _booking(_d(-1), _d(1))


class MovesDb(FakeMotelDb):
    def __init__(self, existing, update_ok=True):
        super().__init__([_room("1"), _room("2"), _room("3")])
        self.existing = [dict(e) for e in existing]
        self.update_motel_reservation = AsyncMock(return_value={"$id": "old1"} if update_ok else None)

    async def lookup_motel_reservation(self, **kwargs):
        return [dict(e) for e in self.existing]

    async def get_booking_by_reference(self, ref, tenant_id="coalcreek"):
        return next((dict(e) for e in self.existing if e["booking_reference"] == ref), None)


@pytest.fixture(autouse=True)
def pms_mode(monkeypatch):
    from core import config as _cfg
    monkeypatch.setattr(_cfg.settings, "USE_LIVE_SCRAPING", False)


def _args(ci, co, **extra):
    return {"guest_name": "Priya Nair", "check_in_date": ci, "check_out_date": co, "room_type": "queen",
            "guest_email": "priya.nair@example.com", "has_user_confirmed_summary": True,
            "_user_utterance": "yes, that's right", **extra}


async def _book(db, ci=None, co=None, **extra):
    return await ch.handle_create_booking_request(
        args=_args(ci or _d(16), co or _d(18), **extra), user_phone=CALLER,
        save_reservation_fn=db.save, db_service=db)


# ── the rule for each kind of booking ────────────────────────────────────────

@pytest.mark.parametrize("doc, kind, words", [
    (PAID_AHEAD, "paid", "reception"),
    (PAID_OVER, "finished", "FINISHED STAY"),
    (UNPAID_AHEAD, "movable", "replaces_booking_reference"),
    (STAYING_NOW, "in_house", "STAYING NOW"),
    (_booking(_d(9), _d(11), payment="card_on_file"), "paid", "reception"),
    (_booking(_d(9), _d(11), payment=""), "paid", "reception"),            # walk-in, paid at the desk
    (_booking(_d(9), _d(11), status="expired", payment="pending_payment"), "released", "no longer active"),
    (_booking(_d(9), _d(11), status="cancelled", payment="pending_payment"), "released", "no longer active"),
    (_booking(_d(-5), _d(-3), status="pending", payment="pending_payment"), "finished", "FINISHED STAY"),
])
def test_change_rule(doc, kind, words):
    got_kind, rule = ch._change_rule(doc, ch._today_melbourne_date())
    assert got_kind == kind and words in rule, (got_kind, rule)


def test_a_finished_stay_says_how_long_ago():
    _, rule = ch._change_rule(PAID_OVER, ch._today_melbourne_date())
    assert "3 days ago" in rule and "say first that this stay has already finished" in rule


def test_checkout_day_is_its_own_case():
    """Still in the room this morning: not "staying on", not "over" — reception
    handles a late checkout or an extra night, and nothing is moved."""
    today = ch._today_melbourne_date()
    assert ch._stay_timing(_booking(_d(-2), _d(0)), today) == "checkout_today"
    kind, rule = ch._change_rule(_booking(_d(-2), _d(0)), today)
    assert kind == "in_house" and "CHECK OUT TODAY" in rule and "FINISHED" not in rule
    assert ch._stay_timing(_booking(_d(-3), _d(-1)), today) == "finished"


# ── the rule reaches the model ───────────────────────────────────────────────

@pytest.mark.parametrize("doc, timing, words", [
    (PAID_OVER, "finished", "FINISHED STAY"),
    (PAID_AHEAD, "upcoming", "reception"),
    (UNPAID_AHEAD, "upcoming", "you can move it yourself"),
])
async def test_lookup_booking_carries_the_rule(doc, timing, words):
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[doc])
    result = await ch.handle_lookup_booking({"guest_name": "Priya Nair"}, db, CALLER)
    assert result["found"] and result["stay_timing"] == timing and words in result["change_rule"]


async def test_the_call_state_note_says_a_finished_stay_is_over():
    """The probe's own setup: the booking reaches the model as a CALL STATE note."""
    db = MagicMock()
    db.lookup_motel_reservation = AsyncMock(return_value=[PAID_OVER])
    result = await ch.handle_lookup_booking({"guest_name": "Priya Nair"}, db, CALLER)
    state = CallState()
    state.observe("lookup_booking", {"guest_name": "Priya Nair"}, result)
    note = state.as_note()
    assert "- Changing or moving it: FINISHED STAY" in note
    assert "cannot be moved or changed" in note


# ── create_booking_request refuses what the prompt alone did not ─────────────

async def test_a_paid_stay_is_not_moved_by_a_new_hold():
    db = MovesDb([PAID_AHEAD])
    out = await _book(db, replaces_booking_reference="CC-41273")
    assert out["success"] is False and out["move_refused"] == "paid" and "reception" in out["error"]
    assert db.saved == [] and not db.update_motel_reservation.await_count


async def test_a_finished_stay_is_not_moved():
    db = MovesDb([PAID_OVER])
    out = await _book(db, replaces_booking_reference="cc 41273")      # spoken, spaced
    assert out["move_refused"] == "finished" and "already finished" in out["error"]
    assert db.saved == []


async def test_a_stay_in_progress_is_not_moved():
    db = MovesDb([STAYING_NOW])
    out = await _book(db, replaces_booking_reference="CC-41273")
    assert out["move_refused"] == "in_house" and db.saved == []


async def test_new_dates_from_a_caller_with_a_paid_booking_need_their_intent():
    """The probe's paid-ahead failure: the model books the new weekend as if new."""
    db = MovesDb([PAID_AHEAD])
    out = await _book(db)
    assert out["success"] is False and out["needs_intent"] is True and out["existing_booking"] == "CC-41273"
    assert "INSTEAD" in out["error"] and "it is paid" in out["error"] and "transfer_to_staff" in out["error"]
    assert db.saved == []


async def test_a_second_stay_is_booked_once_the_caller_says_so():
    db = MovesDb([PAID_AHEAD])
    out = await _book(db, additional_stay=True)
    assert out["success"] is True and len(db.saved) == 1
    assert not db.update_motel_reservation.await_count            # the paid booking is untouched


async def test_a_returning_guest_with_only_a_finished_stay_books_freely():
    """A finished stay is history, not a live booking: no question to answer."""
    db = MovesDb([PAID_OVER])
    out = await _book(db)
    assert out["success"] is True and len(db.saved) == 1


async def test_an_unpaid_hold_is_moved_and_the_old_one_released():
    """The control: refusing this is a miss."""
    db = MovesDb([UNPAID_AHEAD])
    out = await _book(db, replaces_booking_reference="CC-41273")
    assert out["success"] is True and len(db.saved) == 1
    assert out["replaced_booking_reference"] == "CC-41273" and out["old_hold_released"] is True
    assert out["message"].startswith("I've moved your booking")
    call = db.update_motel_reservation.await_args.kwargs
    assert call["booking_id"] == "old1" and call["data"]["status"] == "cancelled"
    assert out["booking_reference"] in call["data"]["notes"]


async def test_new_dates_from_a_caller_with_an_unpaid_hold_need_their_intent_too():
    db = MovesDb([UNPAID_AHEAD])
    out = await _book(db)
    assert out["needs_intent"] is True and 'replaces_booking_reference="CC-41273"' in out["error"]
    assert db.saved == []


async def test_a_failed_release_is_reported_not_hidden():
    db = MovesDb([UNPAID_AHEAD], update_ok=False)
    out = await _book(db, replaces_booking_reference="CC-41273")
    assert out["success"] is True and out["old_hold_released"] is False


async def test_moving_a_reference_that_is_not_theirs_is_refused():
    db = MovesDb([UNPAID_AHEAD])
    out = await _book(db, replaces_booking_reference="CC-99999")
    assert out["success"] is False and "no booking CC-99999" in out["error"] and db.saved == []


async def test_someone_elses_booking_on_the_list_is_not_a_reason_to_ask():
    """The guard looks at the caller's own bookings only."""
    other = dict(PAID_AHEAD, guest_phone="+61400000001")
    db = MovesDb([other])
    out = await _book(db)
    assert out["success"] is True


async def test_an_expired_hold_is_not_a_live_booking():
    db = MovesDb([_booking(_d(9), _d(11), status="expired", payment="pending_payment")])
    out = await _book(db)
    assert out["success"] is True


async def test_the_new_hold_carries_its_own_rule_into_the_call_state():
    db = MovesDb([])
    out = await _book(db)
    assert out["success"] and "you can move it yourself" in out["change_rule"]


# ── found by the independent review ────────────────────────────────────────

async def test_naming_a_lapsed_hold_does_not_skip_the_live_booking_check():
    expired = _booking(_d(9), _d(11), ref="CC-11111", status="expired", payment="pending_payment", doc_id="e1")
    db = MovesDb([expired, PAID_AHEAD])
    out = await _book(db, replaces_booking_reference="CC-11111")
    assert out["success"] is False and out["needs_intent"] is True and db.saved == []


async def test_with_no_caller_number_nobody_elses_booking_is_read_back_or_cancelled():
    db = MovesDb([UNPAID_AHEAD])
    out = await ch.handle_create_booking_request(
        args=_args(_d(16), _d(18), guest_phone=CALLER, replaces_booking_reference="CC-41273"),
        user_phone="", save_reservation_fn=db.save, db_service=db)
    assert out["success"] is False and "no booking" in out["error"]
    assert "41273" not in out["error"].replace("CC-41273", "") and not db.update_motel_reservation.await_count


async def test_a_hold_can_move_onto_overlapping_nights_when_its_room_is_the_last_one():
    one_room = MovesDb([UNPAID_AHEAD])
    one_room.rooms = [_room("1")]
    one_room.reservations = [{"$id": "old1", "booking_reference": "CC-41273", "room_number": "1",
                              "check_in_date": _d(9), "check_out_date": _d(11), "status": "pending"}]
    out = await _book(one_room, ci=_d(10), co=_d(12), replaces_booking_reference="CC-41273")
    assert out["success"] is True and out["old_hold_released"] is True


async def test_an_old_hold_paid_during_the_call_is_not_cancelled():
    """Through the per-call lookup memo, as the dispatcher really calls it: the
    memo still says unpaid, the database says paid. The database must win."""
    raw = MovesDb([UNPAID_AHEAD])
    raw.get_booking_by_reference = AsyncMock(return_value=dict(UNPAID_AHEAD, status="confirmed",
                                                                payment_status="paid"))
    db = ch._CachedReservationLookup(raw)
    out = await ch.handle_create_booking_request(
        args=_args(_d(16), _d(18), replaces_booking_reference="CC-41273"), user_phone=CALLER,
        save_reservation_fn=raw.save, db_service=db)
    assert out["success"] is True and out["old_hold_released"] is False
    assert not raw.update_motel_reservation.await_count


async def test_the_old_checkout_is_expired_when_a_hold_moves(monkeypatch):
    from services.tenants.coalcreek.stripe import coalcreek_stripe_service
    import stripe as stripe_mod
    monkeypatch.setattr(coalcreek_stripe_service, "configured", True)
    expire = MagicMock()
    monkeypatch.setattr(stripe_mod.checkout.Session, "expire", expire)
    linked = dict(UNPAID_AHEAD, payment_link_url="https://checkout.stripe.com/c/pay/cs_test_a1B2c3#fid")
    db = MovesDb([linked])
    out = await _book(db, replaces_booking_reference="CC-41273")
    assert out["old_hold_released"] is True
    expire.assert_called_once_with("cs_test_a1B2c3")


async def test_expiring_a_link_with_no_session_id_is_a_quiet_no():
    from services.tenants.coalcreek.stripe import coalcreek_stripe_service
    assert await coalcreek_stripe_service.expire_checkout_from_url("https://example.com/pay") is False
