"""
tests/test_stream_auth.py
=========================
The signed `stream_token` that ties a Twilio Media Stream socket to the TwiML
we issued. Without it, anyone who knows /api/voice/stream can open the socket,
send a `start` claiming a guest's number, and pass the "caller owns this
booking" gates. These pin the token itself, the off/report/enforce rollout
switch, the orchestrator's handling of a bad start, and the TwiML producers.
"""
import json
import logging
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import stream_auth
from core.config import settings
from core.stream_auth import (
    TOKEN_TTL_S,
    check_stream_start,
    issue_stream_token,
    resolve_mode,
    stream_auth_mode,
    verify_stream_token,
)
from services.voice_agent.cascaded_orchestrator import CascadedPipelineOrchestrator

NOW = 1_800_000_000.0
SID, PHONE, TENANT = "CA0123456789abcdef", "+61400000001", "coalcreek"


@pytest.fixture(autouse=True)
def _fresh_log_once():
    # The once-only misconfiguration logs are module state; each test starts clean.
    stream_auth._logged_once.clear()
    yield
    stream_auth._logged_once.clear()


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

class TestToken:
    def test_round_trip(self):
        token = issue_stream_token(SID, PHONE, TENANT, now=NOW)
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW + 5) == (True, "valid")

    @pytest.mark.parametrize("call_sid,phone,tenant", [
        (SID, "+61400000002", TENANT),     # someone else's number
        (SID, PHONE, "ovela_demo"),        # another tenant
        ("CAdifferentcall0000", PHONE, TENANT),  # token lifted from another call
    ])
    def test_tampered_fields_are_rejected(self, call_sid, phone, tenant):
        token = issue_stream_token(SID, PHONE, TENANT, now=NOW)
        assert verify_stream_token(token, call_sid, phone, tenant, now=NOW) == (False, "bad-signature")

    def test_expired_token_is_rejected(self):
        token = issue_stream_token(SID, PHONE, TENANT, now=NOW)
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW + TOKEN_TTL_S + 1) == (False, "expired")
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW + TOKEN_TTL_S - 1)[0] is True

    def test_token_from_the_future_is_rejected(self):
        token = issue_stream_token(SID, PHONE, TENANT, now=NOW + 3600)
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW) == (False, "issued-in-future")

    def test_rewritten_issue_time_breaks_the_signature(self):
        # Extending a token's life means editing iat, which is inside the MAC.
        v, iat, b, mac = issue_stream_token(SID, PHONE, TENANT, now=NOW).split(".")
        forged = ".".join([v, str(int(iat) + 3600), b, mac])
        assert verify_stream_token(forged, SID, PHONE, TENANT, now=NOW + 3600) == (False, "bad-signature")

    @pytest.mark.parametrize("token,reason", [
        (None, "missing"), ("", "missing"), ("garbage", "malformed"),
        ("v1.notanumber.b.abc", "malformed"), ("v2.1.b.abc", "malformed"),
    ])
    def test_missing_and_malformed(self, token, reason):
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW) == (False, reason)

    def test_unbound_token_pins_phone_and_tenant_but_not_call_sid(self):
        token = issue_stream_token("", PHONE, TENANT, now=NOW)
        assert verify_stream_token(token, "CAanything", PHONE, TENANT, now=NOW) == (True, "valid-unbound")
        assert verify_stream_token(token, "CAanything", "+61499999999", TENANT, now=NOW)[0] is False

    def test_bound_token_cannot_be_relabelled_unbound(self):
        v, iat, _, mac = issue_stream_token(SID, PHONE, TENANT, now=NOW).split(".")
        assert verify_stream_token(f"{v}.{iat}.u.{mac}", "CAother", PHONE, TENANT, now=NOW)[0] is False

    def test_secret_change_invalidates_tokens(self, monkeypatch):
        token = issue_stream_token(SID, PHONE, TENANT, now=NOW)
        monkeypatch.setattr(settings, "STREAM_TOKEN_SECRET", "a-different-secret")
        assert verify_stream_token(token, SID, PHONE, TENANT, now=NOW) == (False, "bad-signature")

    def test_no_secret_degrades_to_off_without_crashing(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "STREAM_TOKEN_SECRET", "")
        monkeypatch.setattr(settings, "APPWRITE_API_KEY", "")
        with caplog.at_level(logging.ERROR, logger="core.stream_auth"):
            assert stream_auth_mode() == "off"
            assert stream_auth_mode() == "off"
        assert issue_stream_token(SID, PHONE, TENANT) == ""
        assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1

    def test_unknown_mode_behaves_as_report(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enfroce")
        with caplog.at_level(logging.WARNING, logger="core.stream_auth"):
            assert resolve_mode("STREAM_AUTH_MODE") == "report"
        assert "enfroce" in caplog.text


# ---------------------------------------------------------------------------
# Verdict on a start payload
# ---------------------------------------------------------------------------

def _start(token=None, phone=PHONE, tenant=TENANT, call_sid=SID):
    params = {"user_phone": phone, "tenant_id": tenant}
    if token is not None:
        params["stream_token"] = token
    return {"streamSid": "MZ1", "callSid": call_sid, "customParameters": params}


class TestCheckStreamStart:
    def test_report_mode_lets_a_bad_start_through_but_says_so(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "report")
        with patch("core.stream_auth.sentry_sdk.capture_message") as capture, \
                caplog.at_level(logging.INFO, logger="core.stream_auth"):
            assert check_stream_start(_start(token="v1.1.b.forged")) is True
        assert "verdict=invalid" in caplog.text
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert capture.call_args.kwargs["level"] == "warning"

    def test_enforce_rejects_missing_and_invalid(self, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enforce")
        assert check_stream_start(_start()) is False
        assert check_stream_start(_start(token="v1.1.b.forged")) is False

    def test_valid_token_is_logged_as_valid_on_every_call(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enforce")
        token = issue_stream_token(SID, PHONE, TENANT)
        with caplog.at_level(logging.INFO, logger="core.stream_auth"):
            assert check_stream_start(_start(token=token)) is True
        assert "verdict=valid" in caplog.text
        # A real call never reaches Sentry.
        assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_off_checks_nothing(self, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "off")
        assert check_stream_start(_start()) is True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZ0")
    agent.warm_llm_on_start = False
    return agent


async def _run(orchestrator, messages):
    """run_loop over `messages` with the real stop(), bridges stubbed."""
    async def fake_iter_text():
        for m in messages:
            yield json.dumps(m)

    orchestrator.twilio_ws.iter_text = fake_iter_text
    greeting, context = AsyncMock(), AsyncMock()
    orchestrator.closed = AsyncMock()   # both bridges' close(), for the asserts
    with patch.object(orchestrator.deepgram, "connect", AsyncMock(return_value=True)), \
         patch.object(orchestrator.cartesia, "connect", AsyncMock(return_value=True)), \
         patch.object(orchestrator.deepgram, "close", orchestrator.closed), \
         patch.object(orchestrator.cartesia, "close", orchestrator.closed), \
         patch.object(orchestrator, "process_deepgram_events", AsyncMock()), \
         patch.object(orchestrator, "trigger_initial_greeting", greeting), \
         patch.object(orchestrator, "_ensure_call_context", context), \
         patch.object(orchestrator, "handle_twilio_audio", AsyncMock()) as audio:
        await orchestrator.run_loop()
    return greeting, context, audio


class TestOrchestratorGate:
    async def test_report_mode_runs_the_call_despite_a_bad_token(self, orchestrator, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "report")
        greeting, context, _ = await _run(orchestrator, [
            {"event": "connected"},
            {"event": "start", "start": _start(token="v1.1.b.forged")},
            {"event": "stop"},
        ])
        greeting.assert_called_once()
        context.assert_called_once()
        assert orchestrator.user_phone == PHONE
        orchestrator.twilio_ws.close.assert_not_called()

    async def test_enforce_closes_the_socket_and_never_greets(self, orchestrator, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enforce")
        greeting, context, audio = await _run(orchestrator, [
            {"event": "connected"},
            {"event": "start", "start": _start(token="v1.1.b.forged", phone="+61400000002")},
            {"event": "media", "media": {"payload": "AAAA"}},
            {"event": "stop"},
        ])
        orchestrator.twilio_ws.close.assert_awaited_once_with(code=1008)
        greeting.assert_not_called()
        context.assert_not_called()      # no caller lookup / tenant load
        audio.assert_not_called()        # nothing after the start is read
        # The forged identity was never adopted, and stop() left nothing running.
        assert orchestrator.user_phone == ""
        assert orchestrator.is_running is False
        assert orchestrator._turn_worker_task.done()
        assert orchestrator.closed.await_count == 2   # Deepgram + Cartesia

    async def test_enforce_rejects_audio_sent_before_any_start(self, orchestrator, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enforce")
        greeting, _, audio = await _run(orchestrator, [
            {"event": "connected"},
            {"event": "media", "media": {"payload": "AAAA"}},
        ])
        orchestrator.twilio_ws.close.assert_awaited_once_with(code=1008)
        audio.assert_not_called()
        greeting.assert_not_called()

    async def test_enforce_admits_a_valid_token(self, orchestrator, monkeypatch):
        monkeypatch.setattr(settings, "STREAM_AUTH_MODE", "enforce")
        token = issue_stream_token(SID, PHONE, TENANT)
        greeting, _, audio = await _run(orchestrator, [
            {"event": "connected"},
            {"event": "start", "start": _start(token=token)},
            {"event": "media", "media": {"payload": "AAAA"}},
            {"event": "stop"},
        ])
        greeting.assert_called_once()
        audio.assert_called_once()
        orchestrator.twilio_ws.close.assert_not_called()
        assert orchestrator.user_phone == PHONE


# ---------------------------------------------------------------------------
# TwiML producers
# ---------------------------------------------------------------------------

def _stream_params(twiml: str) -> dict:
    root = ET.fromstring(twiml.encode("utf-8"))
    streams = root.findall("./Connect/Stream")
    assert len(streams) == 1
    return {p.get("name"): p.get("value") for p in streams[0].findall("Parameter")}


class TestTwiml:
    @pytest.fixture
    def client(self, monkeypatch):
        import api.twilio as twilio_api
        import api.voice as voice_api
        monkeypatch.setattr(settings, "TWILIO_SIGNATURE_MODE", "off")
        monkeypatch.setattr(twilio_api, "_enable_recording", AsyncMock())
        monkeypatch.setattr(voice_api, "_enable_recording", AsyncMock())
        for mod in (twilio_api, voice_api):
            monkeypatch.setattr(mod.db_service, "check_voice_rate_limit", AsyncMock(return_value=(True, "")))
        app = FastAPI()
        app.include_router(twilio_api.router, prefix="/twilio")
        app.include_router(voice_api.router, prefix="/api/voice")
        return TestClient(app)

    def test_voice_webhook_carries_a_token_that_verifies(self, client):
        r = client.post("/twilio/voice?tenant_id=coalcreek",
                        data={"CallSid": SID, "From": PHONE, "To": "+61348236219"})
        assert r.status_code == 200
        params = _stream_params(r.text)
        assert verify_stream_token(params["stream_token"], SID, PHONE, "coalcreek") == (True, "valid")

    def test_voice_webhook_escapes_a_malicious_from(self, client):
        evil = '"/><Hangup/><Parameter name="x" value="'
        r = client.post("/twilio/voice?tenant_id=coalcreek",
                        data={"CallSid": SID, "From": evil, "To": "+61348236219"})
        root = ET.fromstring(r.text.encode("utf-8"))   # still well-formed
        assert root.find(".//Hangup") is None          # no injected verb
        params = _stream_params(r.text)
        assert set(params) == {"user_phone", "tenant_id", "user_to", "transfer_failed", "stream_token"}
        # Twilio sees the raw value back, and the token was signed over it.
        assert params["user_phone"] == evil
        assert verify_stream_token(params["stream_token"], SID, evil, "coalcreek")[0] is True

    def test_voice_webhook_output_is_otherwise_unchanged(self, client):
        r = client.post("/twilio/voice?tenant_id=coalcreek",
                        data={"CallSid": SID, "From": PHONE, "To": "+61348236219"})
        assert f'<Parameter name="user_phone" value="{PHONE}" />' in r.text
        assert '<Parameter name="transfer_failed" value="false" />' in r.text

    def test_demo_twiml_carries_a_token_that_verifies(self, client):
        r = client.post("/api/voice/twiml?phone=%2B61400000001&tenant_id=ovela_demo&is_demo=true",
                        data={"CallSid": SID, "AnsweredBy": "human"})
        assert r.status_code == 200
        params = _stream_params(r.text)
        assert verify_stream_token(params["stream_token"], SID, PHONE, "ovela_demo") == (True, "valid")
