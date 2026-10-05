"""
Regression tests: staff magic links (api/actions.py) and the incoming-call
forwarder (api/twilio.py) must AWAIT the async db_service methods.

The db fakes below are real `async def`s, exactly like production. Before the
fix every route returned a coroutine-shaped 500 (actions) or the
"technical difficulties" hangup TwiML (twilio). If anyone drops an `await`
again these go red.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.actions as actions
import api.twilio as twilio_api


class _AsyncNotificationsDB:
    """Async fake mirroring NotificationsMixin's signatures."""

    def __init__(self, notifications):
        self.notifications = notifications
        self.updates = []

    async def get_staff_notifications(self, *args, **kwargs):
        return self.notifications

    async def update_staff_notification(self, notification_id, data):
        self.updates.append((notification_id, data))
        return {"$id": notification_id, **data}


@pytest.fixture
def client_and_db(monkeypatch):
    db = _AsyncNotificationsDB([
        {"$id": "n1", "status": "pending", "customer_name": "Guest",
         "customerPhone": "+61400000000", "extra_data": json.dumps({})},
    ])
    monkeypatch.setattr(actions, "db_service", db)
    # Token crypto is not under test here — accept any token for n1.
    monkeypatch.setattr(
        actions, "verify_action_token",
        lambda token: (True, {"notification_id": "n1"}, None),
    )
    app = FastAPI()
    app.include_router(actions.router)
    # raise_server_exceptions=False so a regression shows up as a 500 assertion
    # rather than a TypeError traceback from inside the route.
    return TestClient(app, raise_server_exceptions=False), db


@pytest.mark.parametrize("path,expected_status", [
    ("/actions/complete", "completed"),
    ("/actions/dismiss", "dismissed"),
    ("/actions/reject", "rejected"),
    ("/actions/approve", "completed"),
])
def test_magic_link_routes_await_db(client_and_db, path, expected_status):
    client, db = client_and_db
    # The action runs on the POST behind the confirm page (GET only confirms).
    resp = client.post(path, data={"token": "t"})
    assert resp.status_code == 200, resp.text
    assert db.updates and db.updates[-1][0] == "n1"
    assert db.updates[-1][1]["status"] == expected_status


def test_update_route_awaits_db_and_redirects(client_and_db):
    client, db = client_and_db
    resp = client.post("/actions/update", data={"token": "t"}, follow_redirects=False)
    assert resp.status_code == 303
    assert db.updates == [("n1", {"status": "in_progress"})]


def test_complete_unknown_notification_is_404_not_500(client_and_db):
    client, db = client_and_db
    db.notifications = []
    resp = client.post("/actions/complete", data={"token": "t"})
    assert resp.status_code == 404
    assert db.updates == []


def test_incoming_call_awaits_tenant_settings(monkeypatch):
    class _SettingsDB:
        async def get_tenant_settings(self, tenant_id):
            return {"business_phone": "61399990000"}

    monkeypatch.setattr(twilio_api, "db_service", _SettingsDB())
    app = FastAPI()
    app.include_router(twilio_api.router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/incoming-call", data={
        "CallSid": "CA1", "From": "+61400000000", "To": "+61300000000",
        "CallStatus": "ringing",
    })
    assert resp.status_code == 200
    # Forwarded, not the exception-path hangup.
    assert "<Dial" in resp.text
    assert "+61399990000" in resp.text
    assert "technical difficulties" not in resp.text
