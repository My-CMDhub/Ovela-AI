"""
tests/test_demo_links.py — the demo approval links act on POST, never on GET,
and the public /demo-request form cannot pick a tenant or be sprayed.

Mail security scanners and link previewers fetch every URL in an email by
themselves. When GET /api/voice/demo-approve acted, a scanner placed a real
outbound Twilio call to the lead (and used up the approval) before anyone on the
team clicked. Now GET only verifies the token and renders a confirm page whose
form POSTs the token back; the POST verifies again and acts. Same pattern as
api/actions.py (tests/test_actions_confirm.py). Tokens are real
(services.magic_links), so verification runs end to end.
"""
import re
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.voice as voice
from services.magic_links import generate_action_token

LEAD = {"name": "Ada", "phone": "+61400000001", "business": "Ada's Motel"}


def _token(action, extra=LEAD):
    return generate_action_token("lead1", action, expiry_hours=24, extra_data=extra)


@pytest.fixture
def env(monkeypatch):
    db = AsyncMock()
    db.get_demo_lead.return_value = {"$id": "lead1", "status": "pending_approval"}
    db.update_demo_lead.return_value = {"$id": "lead1"}
    db.create_demo_lead.return_value = {"$id": "lead1"}
    db.check_demo_limit.return_value = True
    monkeypatch.setattr(voice, "db_service", db)
    call = MagicMock(return_value=MagicMock(sid="CA123"))
    monkeypatch.setattr(voice, "_trigger_demo_call", call)
    email = MagicMock()
    email.send_demo_approval_request = AsyncMock()
    monkeypatch.setattr(voice, "email_service", email)
    monkeypatch.setattr(voice, "is_whitelisted", lambda phone: phone == "+61499999999")
    monkeypatch.setattr(voice, "_demo_ip_hits", {})
    app = FastAPI()
    app.include_router(voice.router, prefix="/api/voice")
    return TestClient(app, raise_server_exceptions=False), db, call, email


# --- demo-approve / demo-reject: GET confirms, POST acts ----------------------

@pytest.mark.parametrize("action", ["demo-approve", "demo-reject"])
def test_get_shows_confirm_page_and_changes_nothing(env, action):
    client, db, call, _ = env
    token = _token(action)
    for _ in range(3):  # scanner + link preview + human
        resp = client.get(f"/api/voice/{action}", params={"token": token})
        assert resp.status_code == 200
        assert '<form method="post">' in resp.text
        assert re.search(r'name="token" value="([^"]+)"', resp.text).group(1) == token
        assert resp.headers["cache-control"] == "no-store"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "no-referrer"
    # The whole point: nobody is called and the lead is not even read.
    call.assert_not_called()
    db.get_demo_lead.assert_not_awaited()
    db.update_demo_lead.assert_not_awaited()


def test_post_approve_calls_the_lead(env):
    client, db, call, _ = env
    resp = client.post("/api/voice/demo-approve", data={"token": _token("demo-approve")})
    assert resp.status_code == 200 and "Demo Approved" in resp.text
    call.assert_called_once()
    assert call.call_args.args[:3] == ("Ada", "Ada's Motel", "+61400000001")
    statuses = [c.kwargs["data"]["status"] for c in db.update_demo_lead.await_args_list]
    assert statuses == ["approved", "called"]


def test_post_approve_twice_calls_once(env):
    client, db, call, _ = env
    token = _token("demo-approve")
    assert client.post("/api/voice/demo-approve", data={"token": token}).status_code == 200
    db.get_demo_lead.return_value = {"$id": "lead1", "status": "called"}
    resp = client.post("/api/voice/demo-approve", data={"token": token})
    assert "Already Processed" in resp.text
    call.assert_called_once()


def test_post_reject_marks_lead_rejected(env):
    client, db, call, _ = env
    resp = client.post("/api/voice/demo-reject", data={"token": _token("demo-reject")})
    assert resp.status_code == 200 and "Demo Rejected" in resp.text
    assert db.update_demo_lead.await_args.kwargs["data"]["status"] == "rejected"
    call.assert_not_called()


@pytest.mark.parametrize("action", ["demo-approve", "demo-reject"])
@pytest.mark.parametrize("token", [
    "not-a-jwt",
    jwt.encode({"identifier": "lead1", "action": "demo-approve", "extra": LEAD},
               "wrong-key", algorithm="HS256"),
])
def test_bad_token_rejected_on_get_and_post(env, action, token):
    client, db, call, _ = env
    get = client.get(f"/api/voice/{action}", params={"token": token})
    post = client.post(f"/api/voice/{action}", data={"token": token})
    assert get.status_code == 400 and "Link Invalid" in get.text and "<form" not in get.text
    assert post.status_code == 400 and "Link Invalid" in post.text
    call.assert_not_called()
    db.update_demo_lead.assert_not_awaited()


@pytest.mark.parametrize("token_action,path", [
    ("demo-reject", "demo-approve"),   # the reject link must never place the call
    ("demo-approve", "demo-reject"),
    ("approve", "demo-approve"),       # a staff booking link is not a demo link
])
def test_token_only_works_on_its_own_link(env, token_action, path):
    client, db, call, _ = env
    token = _token(token_action)
    assert client.get(f"/api/voice/{path}", params={"token": token}).status_code == 400
    assert client.post(f"/api/voice/{path}", data={"token": token}).status_code == 400
    call.assert_not_called()
    db.update_demo_lead.assert_not_awaited()


def test_visitor_typed_values_are_escaped(env):
    # name/business come straight from the public website form.
    client, _, _, _ = env
    token = _token("demo-approve", {"name": "<script>x()</script>", "phone": "+61400000001",
                                    "business": "<b>B</b>"})
    page = client.get("/api/voice/demo-approve", params={"token": token}).text
    done = client.post("/api/voice/demo-approve", data={"token": token}).text
    for text in (page, done):
        assert "<script>x()</script>" not in text
        assert "&lt;script&gt;" in text
    assert "<b>B</b>" not in page


# --- demo-request: tenant whitelist ---------------------------------------------

FORM = {"name": "Ada", "business_name": "Ada's Motel", "phone": "+61400000001", "consent": True}


@pytest.mark.parametrize("sent", [None, "coalcreek", "some_other_motel"])
def test_public_request_always_uses_demo_tenant(env, sent):
    client, db, call, _ = env
    body = dict(FORM, **({"tenant_id": sent} if sent else {}))
    resp = client.post("/api/voice/demo-request", json=body)
    assert resp.status_code == 200 and resp.json()["status"] == "pending"
    assert db.check_demo_limit.await_args.args[1] == "ovela_demo"
    assert db.create_demo_lead.await_args.kwargs["tenant_id"] == "ovela_demo"
    call.assert_not_called()


@pytest.mark.parametrize("sent,used", [
    ("coalcreek", "coalcreek"),            # a known tenant: admin demos its agent
    ("some_other_motel", "ovela_demo"),    # unknown: never trusted, even for admins
    (None, "ovela_demo"),                  # used to reach quote(None) and 500
])
def test_admin_phone_may_pick_only_a_known_tenant(env, sent, used):
    client, db, call, _ = env
    body = dict(FORM, phone="+61499999999", tenant_id=sent)
    resp = client.post("/api/voice/demo-request", json=body)
    assert resp.status_code == 200 and resp.json()["status"] == "success"
    assert call.call_args.args[3] == used
    assert db.create_demo_lead.await_args.kwargs["tenant_id"] == used


# --- demo-request: per-IP cap -----------------------------------------------------

def _post_from(client, xff, phone="+61400000001"):
    return client.post("/api/voice/demo-request", json=dict(FORM, phone=phone),
                       headers={"X-Forwarded-For": xff})


def test_ip_cap_blocks_a_spray_but_not_other_visitors(env):
    client, db, _, _ = env
    for i in range(voice._DEMO_IP_LIMIT):
        # Each request a new phone (beating the per-phone limit) and a new forged
        # first hop; Heroku appends the real address last, which is what counts.
        assert _post_from(client, f"10.0.0.{i}, 203.0.113.7", phone=f"+614000{i:05d}").status_code == 200
    blocked = _post_from(client, "10.9.9.9, 203.0.113.7", phone="+61400099999")
    assert blocked.status_code == 429
    assert "try again" in blocked.json()["detail"]
    assert db.create_demo_lead.await_count == voice._DEMO_IP_LIMIT
    # Someone else is unaffected.
    assert _post_from(client, "198.51.100.2").status_code == 200


def test_admin_phone_skips_ip_cap(env):
    client, _, call, _ = env
    for _ in range(voice._DEMO_IP_LIMIT + 2):
        assert _post_from(client, "203.0.113.7", phone="+61499999999").status_code == 200
    assert call.call_count == voice._DEMO_IP_LIMIT + 2


def test_ip_allowance_returns_after_the_window(monkeypatch):
    monkeypatch.setattr(voice, "_demo_ip_hits", {})
    for _ in range(voice._DEMO_IP_LIMIT):
        assert voice._demo_ip_allowed("203.0.113.7", now=1000.0)
    assert not voice._demo_ip_allowed("203.0.113.7", now=1000.0 + voice._DEMO_IP_WINDOW_S - 1)
    assert voice._demo_ip_allowed("203.0.113.7", now=1000.0 + voice._DEMO_IP_WINDOW_S)


def test_ip_tracking_stays_bounded(monkeypatch):
    monkeypatch.setattr(voice, "_demo_ip_hits", {})
    monkeypatch.setattr(voice, "_DEMO_IP_MAX_TRACKED", 50)
    for i in range(50):
        voice._demo_ip_allowed(f"old{i}", now=0.0)
    voice._demo_ip_allowed("new", now=voice._DEMO_IP_WINDOW_S + 1.0)
    assert list(voice._demo_ip_hits) == ["new"]


def test_client_ip_reads_the_last_hop_across_repeated_header_lines():
    """A client can send X-Forwarded-For twice; the router's appended hop may sit
    on the later line. Reading only the first line returned a client-typed value."""
    from starlette.requests import Request
    from api.voice import _client_ip

    scope = {
        "type": "http", "method": "POST", "path": "/api/voice/demo-request",
        "headers": [(b"x-forwarded-for", b"6.6.6.6"), (b"x-forwarded-for", b"7.7.7.7, 203.0.113.9")],
        "client": ("10.0.0.1", 1234),
    }
    assert _client_ip(Request(scope)) == "203.0.113.9"
