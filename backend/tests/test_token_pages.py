"""Token-bearing pages never leak their URL through Referer or a shared cache."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from core.token_pages import no_referrer_on_token_pages


def _client():
    app = FastAPI()
    app.middleware("http")(no_referrer_on_token_pages)

    @app.post("/api/actions/complete")
    async def done():
        return HTMLResponse("<a href='https://ovela.dev'>Open Dashboard</a>")

    @app.get("/api/voice/demo-approve")
    async def demo():
        return HTMLResponse("ok", headers={"Referrer-Policy": "same-origin"})

    @app.get("/api/dashboard/stats")
    async def stats():
        return {"ok": True}

    return TestClient(app)


def test_result_pages_under_actions_send_no_referrer():
    r = _client().post("/api/actions/complete")
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"


def test_a_page_that_sets_its_own_policy_keeps_it():
    assert _client().get("/api/voice/demo-approve").headers["referrer-policy"] == "same-origin"


def test_other_routes_are_untouched():
    assert "referrer-policy" not in _client().get("/api/dashboard/stats").headers
