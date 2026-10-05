"""
tests/test_dashboard_auth.py — dashboard and notification writes need a signed-in
user, and only ever touch that user's tenant.

The read routes always required an Appwrite JWT (core.auth.get_current_tenant_id),
but the writes took none: anyone on the internet could approve or reject a booking,
send its payment link, file walk-ins, or overwrite a motel's staff email (where
booking approvals and callback requests are sent). Settings and notifications also
trusted ?tenant_id=, so a caller picked whose data they acted on.

Contract pinned here:
  - no Authorization header -> 401 before any Appwrite call;
  - the tenant is the JWT's; ?tenant_id= / body tenant_id are ignored;
  - another tenant's booking is the same 404 as a missing one (no existence oracle).

get_current_tenant_id is replaced via app.dependency_overrides for the signed-in
cases; for the 401 cases the real dependency runs (it rejects a missing header
before any network call).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_tenant_id, get_optional_tenant_id


TENANT = "tenant_a"
OTHER = "tenant_b"


def _booking(tenant_id, **extra):
    doc = {"$id": "b1", "tenant_id": tenant_id, "booking_reference": "CC-1",
           "status": "pending", "guest_name": "Test Guest"}
    doc.update(extra)
    return doc


@pytest.fixture
def env(monkeypatch):
    """Dashboard + notifications routers, Appwrite and db_service mocked out."""
    from api import dashboard, notifications
    from services.appwrite import db_service

    appwrite = AsyncMock(return_value={"$id": "b1"})
    monkeypatch.setattr(dashboard, "appwrite_request", appwrite)
    monkeypatch.setattr(db_service, "get_tenant_settings", AsyncMock(return_value={
        "business_name": "A Motel", "owner_email": "owner@a.example",
        "staff_email": "staff@a.example", "business_phone": "0400000000",
        "industry": "hospitality",
    }))
    monkeypatch.setattr(db_service, "update_tenant_settings", AsyncMock(return_value=True))
    monkeypatch.setattr(db_service, "get_tenant_config", AsyncMock(return_value={
        "use_stripe_payments": False, "business_name": "A Motel"}))

    notif_db = AsyncMock()
    notif_db.get_staff_notifications.return_value = [
        {"$id": "n1", "status": "pending", "tenant_id": TENANT}]
    notif_db.update_staff_notification.return_value = {"$id": "n1"}
    notif_db.create_staff_notification.return_value = {"$id": "n2"}
    monkeypatch.setattr(notifications, "db_service", notif_db)

    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/dashboard")
    app.include_router(notifications.router, prefix="/api/dashboard")
    client = TestClient(app, raise_server_exceptions=False)

    def sign_in(tenant=TENANT):
        app.dependency_overrides[get_current_tenant_id] = lambda: tenant
        app.dependency_overrides[get_optional_tenant_id] = lambda: tenant

    return client, appwrite, db_service, notif_db, sign_in


WRITE_ROUTES = [
    ("POST", "/api/dashboard/reservations/manual",
     {"guest_name": "G", "guest_phone": "1", "check_in_date": "2026-11-01",
      "check_out_date": "2026-11-02"}),
    ("PATCH", "/api/dashboard/bookings/b1", {"notes": "x"}),
    ("POST", "/api/dashboard/bookings/b1/approve", None),
    ("POST", "/api/dashboard/bookings/b1/reject", None),
    ("POST", "/api/dashboard/bookings/b1/payment-link", None),
    ("POST", "/api/dashboard/settings", {"staff_email": "attacker@evil.example"}),
    ("POST", "/api/dashboard/notifications",
     {"customer_name": "C", "customer_phone": "1", "reason": "r"}),
    ("PATCH", "/api/dashboard/notifications/n1", {"status": "completed"}),
    ("DELETE", "/api/dashboard/notifications/n1", None),
    ("POST", "/api/dashboard/notifications/n1/restore", None),
]


@pytest.mark.parametrize("method,path,body", WRITE_ROUTES)
def test_write_routes_reject_anonymous_callers(env, method, path, body):
    client, appwrite, db_service, notif_db, _ = env
    resp = client.request(method, path, json=body)
    assert resp.status_code == 401, resp.text
    appwrite.assert_not_awaited()
    db_service.update_tenant_settings.assert_not_awaited()
    notif_db.update_staff_notification.assert_not_awaited()
    notif_db.create_staff_notification.assert_not_awaited()


@pytest.mark.parametrize("path", [
    "/api/dashboard/notifications",
    "/api/dashboard/notifications/counts",
    "/api/dashboard/notifications/n1",
])
def test_notification_reads_reject_anonymous_callers(env, path):
    client, _, _, notif_db, _ = env
    # Callers' names and phone numbers: no longer readable with ?tenant_id= alone.
    resp = client.get(path, params={"tenant_id": TENANT})
    assert resp.status_code == 401
    notif_db.get_staff_notifications.assert_not_awaited()


# --- bookings: cross-tenant is a 404, same-tenant works ----------------------

BOOKING_ROUTES = [
    ("PATCH", "/api/dashboard/bookings/b1", {"notes": "x"}),
    ("POST", "/api/dashboard/bookings/b1/approve", None),
    ("POST", "/api/dashboard/bookings/b1/reject", None),
    ("POST", "/api/dashboard/bookings/b1/payment-link", None),
]


@pytest.mark.parametrize("method,path,body", BOOKING_ROUTES)
def test_other_tenants_booking_is_404_and_untouched(env, method, path, body):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    appwrite.return_value = _booking(OTHER)
    resp = client.request(method, path, json=body)
    assert resp.status_code == 404
    # Only the ownership lookup ran; nothing was written.
    assert [c.args[0] for c in appwrite.await_args_list] == ["GET"]


@pytest.mark.parametrize("method,path,body", BOOKING_ROUTES)
def test_missing_booking_looks_identical_to_other_tenants(env, method, path, body):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    appwrite.return_value = _booking(OTHER)
    foreign = client.request(method, path, json=body)
    appwrite.return_value = {"error": "Appwrite error: 404"}
    missing = client.request(method, path, json=body)
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())


@pytest.mark.parametrize("method,path,body", BOOKING_ROUTES)
def test_booking_without_tenant_is_not_claimable(env, method, path, body):
    # Exact match, no "coalcreek" default: a doc with no tenant_id is in nobody's
    # GET /reservations list, so no tenant can act on it either.
    client, appwrite, _, _, sign_in = env
    sign_in("coalcreek")
    appwrite.return_value = {"$id": "b1", "status": "pending"}
    assert client.request(method, path, json=body).status_code == 404


def test_malformed_booking_id_is_404_without_appwrite_call(env):
    client, appwrite, _, _, sign_in = env
    sign_in()
    resp = client.post("/api/dashboard/bookings/b1%3Fx=1/reject")
    assert resp.status_code == 404
    appwrite.assert_not_awaited()


def test_same_tenant_reject_patches_the_booking(env, monkeypatch):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    # Pre-existing, out of scope here: reject_booking imports a module that does
    # not exist (services.tenants.coalcreek.email; the name is unused), so in
    # production it always answers {"success": False}. Stub it to test the
    # ownership path; drop this once that dead import is removed.
    import sys, types
    monkeypatch.setitem(sys.modules, "services.tenants.coalcreek.email",
                        types.SimpleNamespace(coalcreek_email_service=None))
    appwrite.side_effect = [_booking(TENANT), {"$id": "b1", "status": "rejected"}]
    resp = client.post("/api/dashboard/bookings/b1/reject")
    assert resp.status_code == 200 and resp.json()["success"] is True
    method, endpoint, payload = appwrite.await_args_list[1].args
    assert method == "PATCH" and endpoint.endswith("/documents/b1")
    assert payload["data"]["status"] == "rejected"


def test_same_tenant_update_cannot_move_booking_to_another_tenant(env):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    appwrite.side_effect = [_booking(TENANT), {"$id": "b1"}]
    resp = client.patch("/api/dashboard/bookings/b1",
                        json={"notes": "late arrival", "tenant_id": OTHER})
    assert resp.status_code == 200 and resp.json()["success"] is True
    patched = appwrite.await_args_list[1].args[2]["data"]
    assert patched["notes"] == "late arrival"
    assert "tenant_id" not in patched


def test_same_tenant_approve_runs_with_the_jwt_tenant(env):
    client, appwrite, db_service, _, sign_in = env
    sign_in(TENANT)
    appwrite.side_effect = [_booking(TENANT), {"$id": "b1", "status": "approved"}]
    resp = client.post("/api/dashboard/bookings/b1/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    db_service.get_tenant_config.assert_awaited_once_with(TENANT)
    assert appwrite.await_args_list[1].args[0] == "PATCH"


def test_same_tenant_payment_link_returns_existing_link(env):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    appwrite.return_value = _booking(TENANT, payment_link_url="https://pay.example/x",
                                     status="link_sent")
    resp = client.post("/api/dashboard/bookings/b1/payment-link")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "payment_link": "https://pay.example/x"}


def test_manual_booking_is_owned_by_the_jwt_tenant(env, monkeypatch):
    client, appwrite, _, _, sign_in = env
    sign_in(TENANT)
    # Pre-existing, out of scope here: create_manual_booking imports ROOM_INFO,
    # which services.motel_knowledge_base no longer defines, so in production it
    # always answers {"success": False}. Provide it to test tenant ownership.
    from services import motel_knowledge_base
    monkeypatch.setattr(motel_knowledge_base, "ROOM_INFO",
                        {"queen": {"price": 130}}, raising=False)
    resp = client.post("/api/dashboard/reservations/manual", json={
        "guest_name": "G", "guest_phone": "1", "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-02", "tenant_id": OTHER})
    assert resp.status_code == 200 and resp.json()["success"] is True
    method, _, payload = appwrite.await_args.args
    assert method == "POST"
    assert payload["data"]["tenant_id"] == TENANT


# --- settings -----------------------------------------------------------------

def test_settings_write_uses_jwt_tenant_not_query(env):
    client, _, db_service, _, sign_in = env
    sign_in(TENANT)
    resp = client.post("/api/dashboard/settings", params={"tenant_id": OTHER},
                       json={"staff_email": "staff@a.example"})
    assert resp.status_code == 200 and resp.json()["success"] is True
    db_service.update_tenant_settings.assert_awaited_once_with(
        TENANT, {"staff_email": "staff@a.example"})


def test_anonymous_settings_read_returns_only_theming_fields(env):
    client, _, db_service, _, _ = env
    # ThemeContext.tsx: plain fetch, no JWT, reads settings.industry only.
    resp = client.get("/api/dashboard/settings")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "settings": {"industry": "hospitality"}}
    db_service.get_tenant_settings.assert_awaited_once_with("coalcreek")


def test_signed_in_settings_read_is_full_and_for_jwt_tenant(env):
    client, _, db_service, _, sign_in = env
    sign_in(TENANT)
    resp = client.get("/api/dashboard/settings", params={"tenant_id": OTHER})
    assert resp.status_code == 200
    assert resp.json()["settings"]["staff_email"] == "staff@a.example"
    db_service.get_tenant_settings.assert_awaited_once_with(TENANT)


@pytest.mark.asyncio
async def test_optional_tenant_dependency(monkeypatch):
    import core.auth as auth
    assert await auth.get_optional_tenant_id(None) is None
    # A header that is sent is validated exactly like the required dependency
    # (so a bad JWT is a 401, never a silent public view).
    seen = []

    async def fake_required(authorization):
        seen.append(authorization)
        return TENANT

    monkeypatch.setattr(auth, "get_current_tenant_id", fake_required)
    assert await auth.get_optional_tenant_id("Bearer jwt") == TENANT
    assert seen == ["Bearer jwt"]


# --- notifications --------------------------------------------------------------

def test_notifications_are_listed_for_jwt_tenant_not_query(env):
    client, _, _, notif_db, sign_in = env
    sign_in(TENANT)
    resp = client.get("/api/dashboard/notifications", params={"tenant_id": OTHER})
    assert resp.status_code == 200
    assert notif_db.get_staff_notifications.await_args.kwargs["tenant_id"] == TENANT


def test_other_tenants_notification_is_404_and_untouched(env):
    client, _, _, notif_db, sign_in = env
    sign_in(TENANT)
    # n9 belongs to another tenant, so it is absent from this tenant's list.
    resp = client.patch("/api/dashboard/notifications/n9", json={"status": "completed"})
    assert resp.status_code == 404
    notif_db.update_staff_notification.assert_not_awaited()


def test_created_notification_is_owned_by_jwt_tenant(env):
    client, _, _, notif_db, sign_in = env
    sign_in(TENANT)
    resp = client.post("/api/dashboard/notifications", json={
        "customer_name": "C", "customer_phone": "1", "reason": "r", "tenant_id": OTHER})
    assert resp.status_code == 200
    assert notif_db.create_staff_notification.await_args.kwargs["tenant_id"] == TENANT


def test_same_tenant_notification_update_works(env):
    client, _, _, notif_db, sign_in = env
    sign_in(TENANT)
    resp = client.patch("/api/dashboard/notifications/n1", json={"status": "in_progress"})
    assert resp.status_code == 200
    notif_db.update_staff_notification.assert_awaited_once_with("n1", {"status": "in_progress"})
