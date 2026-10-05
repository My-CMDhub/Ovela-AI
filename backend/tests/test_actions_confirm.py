"""
tests/test_actions_confirm.py — staff magic links act on POST, never on GET.

Mail security scanners and link previewers (Outlook Safe Links, Gmail, Slack
unfurls) fetch every URL in an email by themselves. When the links in
api/actions.py mutated on GET, a scanner could complete a callback, or approve or
reject a booking and burn its one-time link, before a human ever clicked.

Now the emailed GET URL only verifies the token and renders a confirm page whose
form POSTs the same token back; the POST verifies again and acts. Tokens here are
real (services.magic_links), so verification is exercised end to end.
"""
import json
import re
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.actions as actions
from services.magic_links import generate_action_token

ACTIONS = ["complete", "dismiss", "reject", "update", "approve"]


@pytest.fixture
def env(monkeypatch):
    db = AsyncMock()
    db.get_staff_notifications.return_value = [
        {"$id": "n1", "status": "pending", "customer_name": "Guest",
         "customerPhone": "+61400000000", "extra_data": json.dumps({})},
    ]
    db.update_staff_notification.return_value = {"$id": "n1"}
    monkeypatch.setattr(actions, "db_service", db)
    app = FastAPI()
    app.include_router(actions.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False), db


@pytest.mark.parametrize("action", ACTIONS)
def test_get_shows_confirm_page_and_changes_nothing(env, action):
    client, db = env
    token = generate_action_token("n1", action)
    resp = client.get(f"/api/actions/{action}", params={"token": token},
                      follow_redirects=False)
    assert resp.status_code == 200
    # A form that POSTs the same token back (no action attr: same URL).
    assert '<form method="post">' in resp.text
    assert re.search(r'name="token" value="([^"]+)"', resp.text).group(1) == token
    # Not cached, not framed (clickjacking a one-click form), no Referer leak.
    assert resp.headers["cache-control"] == "no-store"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    # The whole point: a bot fetching the link touches no data at all.
    db.get_staff_notifications.assert_not_awaited()
    db.update_staff_notification.assert_not_awaited()


def test_get_twice_still_leaves_one_time_link_unused(env):
    client, db = env
    token = generate_action_token("n1", "approve")
    for _ in range(3):  # scanner + preview + human
        assert client.get("/api/actions/approve", params={"token": token}).status_code == 200
    db.update_staff_notification.assert_not_awaited()
    resp = client.post("/api/actions/approve", data={"token": token})
    assert resp.status_code == 200
    assert "Booking Approved" in resp.text
    data = db.update_staff_notification.await_args.args[1]
    assert data["status"] == "completed"
    assert json.loads(data["extra_data"])["link_consumed"] is True


@pytest.mark.parametrize("action,status", [
    ("complete", "completed"), ("dismiss", "dismissed"),
    ("reject", "rejected"), ("approve", "completed"),
])
def test_post_with_valid_token_performs_action(env, action, status):
    client, db = env
    token = generate_action_token("n1", action)
    resp = client.post(f"/api/actions/{action}", data={"token": token})
    assert resp.status_code == 200, resp.text
    assert db.update_staff_notification.await_args.args[0] == "n1"
    assert db.update_staff_notification.await_args.args[1]["status"] == status


def test_post_update_marks_in_progress_and_redirects_with_get(env):
    client, db = env
    token = generate_action_token("n1", "update")
    resp = client.post("/api/actions/update", data={"token": token}, follow_redirects=False)
    # 303, not the default 307: the browser must GET the dashboard, not re-POST.
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("?highlight=n1")
    db.update_staff_notification.assert_awaited_once_with("n1", {"status": "in_progress"})


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("token", ["not-a-jwt", None])
def test_invalid_token_rejected_on_get_and_post(env, action, token):
    client, db = env
    if token is None:  # well-formed but signed with the wrong key
        import jwt
        token = jwt.encode({"identifier": "n1", "action": action}, "wrong-key", algorithm="HS256")
    get = client.get(f"/api/actions/{action}", params={"token": token})
    post = client.post(f"/api/actions/{action}", data={"token": token}, follow_redirects=False)
    assert get.status_code == 400 and "Link Invalid" in get.text
    assert post.status_code == 400 and "Link Invalid" in post.text
    assert "<form" not in get.text
    db.get_staff_notifications.assert_not_awaited()
    db.update_staff_notification.assert_not_awaited()


def test_confirm_page_escapes_token(env, monkeypatch):
    # Only verified tokens are echoed, but the page must never trust that.
    client, _ = env
    monkeypatch.setattr(actions, "verify_action_token",
                        lambda t: (True, {"notification_id": "n1", "action": "complete"}, ""))
    resp = client.get("/api/actions/complete", params={"token": '"><script>x</script>'})
    assert "<script>x</script>" not in resp.text
    assert "&quot;&gt;&lt;script&gt;" in resp.text


@pytest.mark.parametrize("issued_for, posted_to", [
    ("approve", "reject"), ("reject", "approve"), ("complete", "dismiss"), ("dismiss", "complete"),
])
def test_a_token_only_works_for_the_action_it_was_issued_for(env, issued_for, posted_to):
    """The approve link from a staff email used to be accepted by /reject too:
    one email's links decided any outcome, not the one the button named."""
    client, db = env
    token = generate_action_token("n1", issued_for)
    assert client.get(f"/api/actions/{posted_to}", params={"token": token}).status_code == 400
    assert client.post(f"/api/actions/{posted_to}", data={"token": token}).status_code == 400
    db.update_staff_notification.assert_not_awaited()
