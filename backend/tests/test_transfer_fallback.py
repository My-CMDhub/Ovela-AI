"""
tests/test_transfer_fallback.py

A caller asked for a person and nobody answered. Before this, the call came
back to the AI with a fresh "Hello! Thanks for calling", nothing told staff,
and a caller on their second call of the day was hung up on by the rate limit
on the way back. These pin each of those down.
"""
import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import services.transfer_fallback as tf
from core.config import settings
from services.transfer_fallback import (
    TRANSFER_FAILED_LINE,
    TRANSFER_FAILED_NOTE,
    TRANSFER_NOT_STARTED_LINE,
)
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator
from services.voice_agent.vad import ConversationState

SID = "CA" + "a" * 32
CALLER = "+61400111222"


# ── Twilio webhooks ──────────────────────────────────────────────────────────

@pytest.fixture
def twilio_api(monkeypatch):
    import api.twilio as twilio_api
    monkeypatch.setattr(settings, "TWILIO_SIGNATURE_MODE", "off")
    monkeypatch.setattr(twilio_api, "_enable_recording", AsyncMock())
    return twilio_api


@pytest.fixture
def client(twilio_api):
    app = FastAPI()
    app.include_router(twilio_api.router, prefix="/twilio")
    return TestClient(app)


@pytest.fixture
def staff(monkeypatch):
    """The two channels notify_failed_transfer uses, recorded instead of sent."""
    from services.staff_notifications import staff_notification_service
    from services.sms import sms_service
    record = AsyncMock(return_value=True)
    sms = AsyncMock(return_value=True)
    monkeypatch.setattr(staff_notification_service, "notify_new_callback_request", record)
    monkeypatch.setattr(sms_service, "send_sms", sms)
    monkeypatch.setattr(settings, "STAFF_PHONE_NUMBER", "+61399990000")
    return record, sms


class TestTransferStatus:
    @pytest.mark.parametrize("status", ["no-answer", "busy", "failed", "canceled"])
    def test_failed_dial_records_a_callback_and_returns_to_the_ai(self, client, staff, status):
        record, sms = staff
        r = client.post("/twilio/transfer-status?tenant_id=coalcreek", data={
            "CallSid": SID, "From": CALLER, "To": "+61348236219", "DialCallStatus": status,
        })
        assert r.status_code == 200
        assert "<Redirect" in r.text and "transfer_failed=true" in r.text
        # Tenant carried onto the return leg, XML-escaped.
        assert "&amp;tenant_id=coalcreek" in r.text

        record.assert_awaited_once()
        kw = record.await_args.kwargs
        assert kw["customer_phone"] == CALLER          # full number: staff dial it
        assert kw["tenant_id"] == "coalcreek"
        assert status in kw["reason"] and SID in kw["reason"]
        sms.assert_awaited_once()
        assert CALLER in sms.await_args.kwargs["message"]

    def test_redirect_survives_every_notification_channel_raising(self, client, staff):
        record, sms = staff
        record.side_effect = RuntimeError("appwrite down")
        sms.side_effect = RuntimeError("twilio down")
        r = client.post("/twilio/transfer-status", data={
            "CallSid": SID, "From": CALLER, "DialCallStatus": "no-answer",
        })
        assert r.status_code == 200
        assert "/twilio/voice?transfer_failed=true" in r.text
        record.assert_awaited_once()
        sms.assert_awaited_once()      # one channel failing doesn't skip the other

    def test_redirect_survives_scheduling_itself_failing(self, client, staff, monkeypatch):
        import fastapi
        monkeypatch.setattr(fastapi.BackgroundTasks, "add_task",
                            MagicMock(side_effect=RuntimeError("boom")))
        r = client.post("/twilio/transfer-status", data={
            "CallSid": SID, "From": CALLER, "DialCallStatus": "busy",
        })
        assert r.status_code == 200
        assert "transfer_failed=true" in r.text

    @pytest.mark.parametrize("status", ["completed", "answered"])
    def test_answered_transfer_hangs_up_and_notifies_nobody(self, client, staff, status):
        record, sms = staff
        r = client.post("/twilio/transfer-status", data={
            "CallSid": SID, "From": CALLER, "DialCallStatus": status,
        })
        assert "<Hangup/>" in r.text
        record.assert_not_called()
        sms.assert_not_called()


class TestVoiceRateLimitOnReturn:
    @pytest.fixture
    def db(self, twilio_api, monkeypatch):
        limit = AsyncMock(return_value=(False, "user_limit_exceeded"))
        recorded = AsyncMock(return_value=True)
        monkeypatch.setattr(twilio_api.db_service, "check_voice_rate_limit", limit)
        monkeypatch.setattr(twilio_api.db_service, "call_already_recorded", recorded)
        monkeypatch.setattr(twilio_api.db_service, "save_call_transcript", AsyncMock())
        return limit, recorded

    def test_return_leg_of_a_recorded_call_skips_the_rate_limit(self, client, db):
        limit, recorded = db
        r = client.post("/twilio/voice?transfer_failed=true&tenant_id=coalcreek",
                        data={"CallSid": SID, "From": CALLER, "To": "+61348236219"})
        limit.assert_not_called()
        recorded.assert_awaited_once_with(SID, "coalcreek")
        assert "<Connect>" in r.text and "<Hangup/>" not in r.text
        assert '<Parameter name="transfer_failed" value="true" />' in r.text

    def test_flag_without_a_recorded_call_is_still_rate_limited(self, client, db):
        # `?transfer_failed=true` on a brand-new CallSid is not a bypass.
        limit, recorded = db
        recorded.return_value = False
        r = client.post("/twilio/voice?transfer_failed=true&tenant_id=coalcreek",
                        data={"CallSid": SID, "From": CALLER, "To": "+61348236219"})
        limit.assert_awaited_once()
        assert "call limit" in r.text and "<Hangup/>" in r.text

    def test_ordinary_call_is_still_rate_limited(self, client, db):
        limit, recorded = db
        r = client.post("/twilio/voice?tenant_id=coalcreek",
                        data={"CallSid": SID, "From": CALLER, "To": "+61348236219"})
        limit.assert_awaited_once()
        recorded.assert_not_called()
        assert "<Hangup/>" in r.text


class TestCallAlreadyRecorded:
    @pytest.fixture
    def db(self):
        from services.appwrite import db_service
        return db_service

    async def test_existing_call_counts(self, db):
        with patch.object(db, "_make_request", AsyncMock(return_value={"$id": SID, "status": "completed"})) as req:
            assert await db.call_already_recorded(SID, "coalcreek") is True
        assert req.await_args.args[1].endswith(f"/documents/{SID}")

    @pytest.mark.parametrize("doc", [None, {"$id": SID, "status": "blocked"}])
    async def test_missing_or_blocked_call_does_not(self, db, doc):
        with patch.object(db, "_make_request", AsyncMock(return_value=doc)):
            assert await db.call_already_recorded(SID, "coalcreek") is False

    @pytest.mark.parametrize("sid", ["", "../../users", "CA" + "a" * 40])
    async def test_odd_call_sids_never_reach_the_database(self, db, sid):
        with patch.object(db, "_make_request", AsyncMock()) as req:
            assert await db.call_already_recorded(sid, "coalcreek") is False
        req.assert_not_called()

    async def test_unknown_tenant_is_no_not_an_error(self, db):
        assert await db.call_already_recorded(SID, "no_such_tenant") is False


# ── Live pipeline ────────────────────────────────────────────────────────────

@pytest.fixture
def orchestrator():
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZ1")
    agent.is_running = True
    agent.warm_llm_on_start = False
    return agent


async def _run_start(agent, params):
    async def fake_iter_text():
        yield json.dumps({"event": "start", "start": {
            "streamSid": "MZ1", "callSid": SID, "customParameters": params,
        }})
        yield json.dumps({"event": "stop"})

    agent.twilio_ws.iter_text = fake_iter_text
    greeting = AsyncMock()
    with patch.object(agent.deepgram, "connect", AsyncMock(return_value=True)), \
         patch.object(agent.cartesia, "connect", AsyncMock(return_value=True)), \
         patch.object(agent, "process_deepgram_events", AsyncMock()), \
         patch.object(agent, "trigger_initial_greeting", greeting), \
         patch.object(agent, "_ensure_call_context", AsyncMock()), \
         patch.object(agent, "stop", AsyncMock()):
        await agent.run_loop()
        await asyncio.sleep(0)    # let the create_task'd greeting run
    return greeting


class TestOrchestratorReturnLeg:
    async def test_transfer_failed_start_acknowledges_instead_of_greeting(self, orchestrator):
        greeting = await _run_start(orchestrator, {
            "user_phone": CALLER, "tenant_id": "coalcreek", "transfer_failed": "true",
        })
        greeting.assert_called_once_with(TRANSFER_FAILED_LINE, clip="transfer_failed")
        assert {"role": "system", "content": TRANSFER_FAILED_NOTE} in orchestrator.history

    async def test_ordinary_start_greets_as_before(self, orchestrator):
        greeting = await _run_start(orchestrator, {
            "user_phone": CALLER, "tenant_id": "coalcreek", "transfer_failed": "false",
        })
        greeting.assert_called_once_with()
        assert not any(m["role"] == "system" for m in orchestrator.history)

    async def test_transfer_failed_clip_is_what_actually_plays(self, orchestrator):
        sent = []
        orchestrator.twilio_ws.send_text = AsyncMock(side_effect=lambda t: sent.append(json.loads(t)))
        with patch("services.voice_agent.cascaded_orchestrator.asyncio.sleep", AsyncMock()):
            await orchestrator.trigger_initial_greeting(TRANSFER_FAILED_LINE, clip="transfer_failed")

        audio_dir = Path(__file__).resolve().parents[1] / "services/voice_agent/audio/f786b574-daa5-4673-aa0c-cbe3e8534c02"
        first = next(e for e in sent if e["event"] == "media")
        assert base64.b64decode(first["media"]["payload"]) == \
            (audio_dir / "transfer_failed.mulaw.raw").read_bytes()[:1600]
        assert base64.b64decode(first["media"]["payload"]) != \
            (audio_dir / "smart_greeting.mulaw.raw").read_bytes()[:1600]
        assert orchestrator.history[-1] == {"role": "assistant", "content": TRANSFER_FAILED_LINE}
        assert orchestrator.state == ConversationState.AWAITING_INPUT


def _failing_twilio():
    client = AsyncMock()
    client.post = AsyncMock(side_effect=RuntimeError("Twilio 500"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestTransferCallRestFailure:
    @pytest.fixture
    def failing(self, orchestrator):
        orchestrator.call_sid = SID
        orchestrator.user_phone = CALLER
        orchestrator.tenant_id = "coalcreek"
        schedule = MagicMock()
        speak = AsyncMock()
        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient",
                   return_value=_failing_twilio()), \
             patch.object(tf, "schedule_failed_transfer_notification", schedule), \
             patch.object(orchestrator, "trigger_initial_greeting", speak):
            yield orchestrator, schedule, speak

    async def test_records_callback_speaks_and_keeps_the_call(self, failing):
        agent, schedule, speak = failing
        await agent._transfer_call("+61399990000")
        await asyncio.sleep(0)

        assert agent.is_running is True
        schedule.assert_called_once()
        kw = schedule.call_args.kwargs
        assert kw["caller_phone"] == CALLER and kw["call_sid"] == SID and kw["tenant_id"] == "coalcreek"
        assert {"role": "system", "content": TRANSFER_FAILED_NOTE} in agent.history
        speak.assert_called_once_with(TRANSFER_NOT_STARTED_LINE, clip=None,
                                      expected_turn=agent._turn_id)

    async def test_does_not_talk_over_a_turn_that_started_meanwhile(self, failing):
        agent, schedule, speak = failing

        async def caller_spoke_then_fail(*a, **k):
            agent._turn_id += 1          # a new turn took the floor during the request
            raise RuntimeError("Twilio 500")

        ctx = _failing_twilio()
        ctx.__aenter__.return_value.post = AsyncMock(side_effect=caller_spoke_then_fail)
        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=ctx):
            await agent._transfer_call("+61399990000")
        await asyncio.sleep(0)

        schedule.assert_called_once()                 # staff still told
        assert {"role": "system", "content": TRANSFER_FAILED_NOTE} in agent.history
        speak.assert_not_called()

    async def test_a_scheduling_failure_does_not_escape(self, failing):
        agent, schedule, speak = failing
        schedule.side_effect = RuntimeError("no loop")
        await agent._transfer_call("+61399990000")
        assert agent.is_running is True
        speak.assert_called_once()

    async def test_dial_action_carries_the_tenant(self, orchestrator):
        orchestrator.call_sid = SID
        orchestrator.tenant_id = "coalcreek"
        client = AsyncMock()
        client.post = AsyncMock(return_value=MagicMock())
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=ctx):
            await orchestrator._transfer_call("+61399990000")
        assert "transfer-status?tenant_id=coalcreek" in client.post.await_args.kwargs["data"]["Twiml"]


class TestNotifyFailedTransfer:
    async def test_never_raises_and_tries_both_channels(self, staff):
        record, sms = staff
        record.side_effect = RuntimeError("db")
        sms.side_effect = RuntimeError("sms")
        await tf.notify_failed_transfer(caller_phone=CALLER, tenant_id="coalcreek",
                                        call_sid=SID, reason="staff line no-answer")
        record.assert_awaited_once()
        sms.assert_awaited_once()

    async def test_no_staff_phone_means_no_sms(self, staff, monkeypatch):
        record, sms = staff
        monkeypatch.setattr(settings, "STAFF_PHONE_NUMBER", "")
        await tf.notify_failed_transfer(caller_phone=CALLER, tenant_id="coalcreek",
                                        call_sid=SID, reason="x")
        record.assert_awaited_once()
        sms.assert_not_called()

    async def test_caller_number_is_masked_in_logs(self, staff, caplog):
        caplog.set_level("DEBUG")
        await tf.notify_failed_transfer(caller_phone=CALLER, tenant_id="coalcreek",
                                        call_sid=SID, reason="x")
        assert CALLER not in caplog.text

    async def test_scheduled_task_is_held_until_done(self, staff):
        task = tf.schedule_failed_transfer_notification(
            caller_phone=CALLER, tenant_id="coalcreek", call_sid=SID, reason="x")
        assert task in tf._in_flight
        await task
        assert task not in tf._in_flight


class TestReviewFollowUps:
    async def test_a_timed_out_transfer_request_is_not_announced_as_failed(self, orchestrator):
        """A read timeout means Twilio got the request and the answer was lost:
        staff may already be ringing. No 'missed transfer' text, no apology."""
        import httpx
        orchestrator.call_sid = SID
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.ReadTimeout("slow"))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        schedule, speak = MagicMock(), AsyncMock()
        with patch("services.voice_agent.cascaded_orchestrator.httpx.AsyncClient", return_value=ctx), \
             patch.object(tf, "schedule_failed_transfer_notification", schedule), \
             patch.object(orchestrator, "trigger_initial_greeting", speak):
            await orchestrator._transfer_call("+61399990000")
            await asyncio.sleep(0)
        schedule.assert_not_called()
        speak.assert_not_called()
        assert orchestrator.is_running is True

    async def test_a_scripted_line_yields_to_a_turn_that_started_first(self, orchestrator):
        orchestrator._turn_id = 7
        before = list(orchestrator.history)
        await orchestrator.trigger_initial_greeting("Sorry about that.", clip=None, expected_turn=6)
        assert orchestrator._turn_id == 7
        assert orchestrator.history == before

    async def test_a_mid_call_line_starts_with_a_fresh_mark_tracker(self, orchestrator):
        reset = MagicMock()
        orchestrator.mark_tracker.reset = reset
        orchestrator.cartesia.send_transcript_chunk = AsyncMock()
        with patch.object(orchestrator.cartesia, "receive_audio_events", lambda: _empty()):
            task = asyncio.create_task(
                orchestrator.trigger_initial_greeting("Sorry about that.", clip=None))
            await asyncio.sleep(0)
            task.cancel()
            try:
                await task
            except BaseException:
                pass
        reset.assert_called()


async def _empty():
    if False:
        yield {}
