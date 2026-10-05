"""
tests/test_evaluations_adk_auth.py — the ADK query route needs a signed-in user;
evaluation history stays public and read-only.

POST /api/adk/query ran the Gemini agent graph (paid LLM calls) for anyone; it
now takes the tenant from the Appwrite JWT (core.auth.get_current_tenant_id):
no Authorization header is a 401 before any LLM work. GET /evaluations is public
on purpose (the methodology doc links it for verifiability).
"""
import types
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_tenant_id


@pytest.fixture
def evals(monkeypatch):
    import api.evaluations as evaluations
    appwrite = AsyncMock(return_value={"documents": [{"$id": "e1", "run_id": "r1"}], "total": 1})
    monkeypatch.setattr(evaluations, "_appwrite_get", appwrite)
    app = FastAPI()
    app.include_router(evaluations.router, prefix="/api/dashboard")
    app.include_router(evaluations.router, prefix="/api/motel")
    return TestClient(app, raise_server_exceptions=False), app, appwrite


@pytest.mark.parametrize("prefix", ["/api/dashboard", "/api/motel"])
def test_evaluations_are_public_for_verifiability(evals, prefix):
    """docs/EVALUATION_METHODOLOGY.md links the evaluation dashboard publicly so
    anyone can check the published scores; requiring a sign-in broke that link."""
    client, _, appwrite = evals
    resp = client.get(f"{prefix}/evaluations")
    assert resp.status_code == 200
    assert [r["run_id"] for r in resp.json()["runs"]] == ["r1"]


def test_the_evaluations_router_has_no_write_routes():
    import api.evaluations as evaluations
    methods = {m for r in evaluations.router.routes for m in getattr(r, "methods", set())}
    assert methods <= {"GET", "HEAD"}


# --- ADK -----------------------------------------------------------------------

class FakeOrchestrator:
    def __init__(self):
        self.query = AsyncMock(return_value="ok")
        self.update_session_state = AsyncMock()
        self.users = []

    async def get_or_create_session(self, user_id):
        self.users.append(user_id)
        return types.SimpleNamespace(id="s1")


@pytest.fixture
def adk(monkeypatch):
    import sys
    import api.adk as adk_api
    orch = FakeOrchestrator()
    # api/adk.py reads the singleton via `from main import app`. Stand in for
    # main rather than import it (it boots New Relic, Sentry and every router).
    fake_main = types.SimpleNamespace(app=types.SimpleNamespace(
        state=types.SimpleNamespace(adk_orchestrator=orch)))
    monkeypatch.setitem(sys.modules, "main", fake_main)
    app = FastAPI()
    app.include_router(adk_api.router, prefix="/api/adk")
    return TestClient(app, raise_server_exceptions=False), app, orch


def test_adk_query_rejects_anonymous_callers(adk):
    client, _, orch = adk
    resp = client.post("/api/adk/query", json={"call_sid": "CA1", "query": "hi"})
    assert resp.status_code == 401
    orch.query.assert_not_awaited()
    assert orch.users == []


def test_adk_query_works_when_signed_in_and_never_joins_a_live_call(adk):
    client, app, orch = adk
    app.dependency_overrides[get_current_tenant_id] = lambda: "coalcreek"
    resp = client.post("/api/adk/query", json={"call_sid": "CA1", "query": "hi",
                                               "session_state": {"name": "x"}})
    assert resp.status_code == 200, resp.text
    assert resp.json()["response"] == "ok" and resp.json()["call_sid"] == "CA1"
    # The live call's in-process cold path keys its session by the bare CallSid;
    # an HTTP caller gets its own tenant-scoped session instead.
    assert orch.users == ["http:coalcreek:CA1"]
    assert orch.query.await_args.kwargs["user_id"] == "http:coalcreek:CA1"
    assert orch.update_session_state.await_args.kwargs["user_id"] == "http:coalcreek:CA1"


def test_adk_health_stays_public(adk):
    client, _, _ = adk
    assert client.get("/api/adk/health").json()["status"] == "ok"
