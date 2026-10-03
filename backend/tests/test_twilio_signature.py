"""
tests/test_twilio_signature.py
==============================
X-Twilio-Signature on the Twilio webhooks. The signature is over the public
https URL Twilio called (Heroku hands the app http://, so the scheme comes
from X-Forwarded-Proto) plus the form params. "report" must never change a
response; only "enforce" may return 403.
"""
import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from core import stream_auth
from core.config import settings

AUTH_TOKEN = "test-twilio-auth-token"
FORM = {"CallSid": "CA0123456789abcdef", "From": "+61400000001", "To": "+61348236219",
        "CallStatus": "completed", "CallDuration": "12"}


@pytest.fixture(autouse=True)
def _fresh_log_once():
    stream_auth._logged_once.clear()
    yield
    stream_auth._logged_once.clear()


@pytest.fixture
def client(monkeypatch):
    import api.twilio as twilio_api
    import api.voice as voice_api
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    monkeypatch.setattr(settings, "TWILIO_SIGNATURE_MODE", "enforce")
    monkeypatch.setattr(twilio_api, "_enable_recording", AsyncMock())
    monkeypatch.setattr(voice_api, "_enable_recording", AsyncMock())
    for mod in (twilio_api, voice_api):
        monkeypatch.setattr(mod.db_service, "check_voice_rate_limit", AsyncMock(return_value=(True, "")))
    app = FastAPI()
    app.include_router(twilio_api.router, prefix="/twilio")
    app.include_router(voice_api.router, prefix="/api/voice")
    # TestClient talks http://testserver — exactly what the app sees on Heroku.
    return TestClient(app)


def sign(url: str, params: dict) -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(url, params)


def post(client, path, sig, proto="https", data=FORM):
    headers = {"X-Forwarded-Proto": proto}
    if sig is not None:
        headers["X-Twilio-Signature"] = sig
    return client.post(path, data=data, headers=headers)


class TestSignature:
    def test_correct_signature_over_the_https_url_is_accepted(self, client, caplog):
        sig = sign("https://testserver/twilio/call-status", FORM)
        with caplog.at_level(logging.INFO, logger="core.twilio_signature"):
            r = post(client, "/twilio/call-status", sig)
        # 200, not 422: the route's own Form(...) fields still read the body
        # the dependency already parsed.
        assert r.status_code == 200 and r.json() == {"status": "ok"}
        assert "verdict=valid" in caplog.text

    def test_query_string_is_part_of_the_signed_url(self, client):
        url = "https://testserver/twilio/voice?tenant_id=coalcreek"
        r = post(client, "/twilio/voice?tenant_id=coalcreek", sign(url, FORM))
        assert r.status_code == 200 and "<Stream" in r.text
        r = post(client, "/twilio/voice?tenant_id=ovela_demo", sign(url, FORM))
        assert r.status_code == 403

    def test_forwarded_proto_comma_chain_uses_the_first_hop(self, client):
        sig = sign("https://testserver/twilio/call-status", FORM)
        assert post(client, "/twilio/call-status", sig, proto="https, http").status_code == 200

    def test_signature_over_https_fails_if_proto_header_is_absent(self, client):
        # Proves the reconstruction matters: the app alone would check http://.
        sig = sign("https://testserver/twilio/call-status", FORM)
        r = client.post("/twilio/call-status", data=FORM, headers={"X-Twilio-Signature": sig})
        assert r.status_code == 403

    def test_enforce_rejects_bad_tampered_and_missing(self, client):
        good = sign("https://testserver/twilio/call-status", FORM)
        assert post(client, "/twilio/call-status", "bm90LWEtc2lnbmF0dXJl").status_code == 403
        assert post(client, "/twilio/call-status", good,
                    data={**FORM, "From": "+61499999999"}).status_code == 403
        assert post(client, "/twilio/call-status", None).status_code == 403

    def test_report_mode_only_logs(self, client, monkeypatch, caplog):
        monkeypatch.setattr(settings, "TWILIO_SIGNATURE_MODE", "report")
        with patch("core.twilio_signature.sentry_sdk.capture_message") as capture, \
                caplog.at_level(logging.INFO, logger="core.twilio_signature"):
            r = post(client, "/twilio/call-status", "bm90LWEtc2lnbmF0dXJl")
        assert r.status_code == 200
        assert "verdict=invalid" in caplog.text
        assert capture.call_args.kwargs["level"] == "warning"
        # The checked URL is logged without its query (it can carry a phone).
        assert "https://testserver/twilio/call-status" in caplog.text

    def test_no_auth_token_behaves_as_off(self, client, monkeypatch, caplog):
        monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
        with caplog.at_level(logging.ERROR):
            assert post(client, "/twilio/call-status", None).status_code == 200
            assert post(client, "/twilio/call-status", None).status_code == 200
        assert len([r for r in caplog.records if "TWILIO_AUTH_TOKEN" in r.getMessage()]) == 1

    def test_unknown_mode_does_not_reject(self, client, monkeypatch):
        monkeypatch.setattr(settings, "TWILIO_SIGNATURE_MODE", "yes")
        assert post(client, "/twilio/call-status", None).status_code == 200

    def test_every_twilio_route_is_guarded(self, client):
        for path in ("/twilio/voice", "/twilio/incoming-call", "/twilio/recording-status",
                     "/twilio/call-status", "/twilio/sms", "/twilio/transfer-status",
                     "/api/voice/twiml"):
            assert post(client, path, None).status_code == 403, path

    def test_demo_twiml_accepts_a_signed_request(self, client):
        path = "/api/voice/twiml?phone=%2B61400000001&tenant_id=ovela_demo&is_demo=true"
        data = {"CallSid": "CA0123456789abcdef", "AnsweredBy": "human"}
        r = post(client, path, sign(f"https://testserver{path}", data), data=data)
        assert r.status_code == 200 and "stream_token" in r.text
