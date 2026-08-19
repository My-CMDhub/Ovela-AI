"""
tests/test_tenant_config_lookup.py
==================================
Tenant config is on the critical path of the first voice turn: `voice_settings`
(voice, TTS model, Flux turn thresholds) are not applied until it returns.

Measured on Heroku v406, first call after a dyno boot: `Call context ready`
landed 4,316 ms after the Twilio stream started, and the log showed a wasted
round trip — GET .../documents/coalcreek returned 404 before the slug query
found the row. On the second call it was 2 ms (warm imports + cache hit).
"""

import time
import pytest
from unittest.mock import AsyncMock

import services.db.settings as settings_module


@pytest.fixture(autouse=True)
def clear_tenant_cache():
    settings_module._tenant_config_cache.clear()
    yield
    settings_module._tenant_config_cache.clear()


class _Db(settings_module.SettingsMixin):
    """Minimal host for the mixin — only `motel_db_id` and `_make_request`."""
    motel_db_id = "testdb"


@pytest.fixture
def db():
    return _Db()


class TestTenantConfigLookup:
    @pytest.mark.asyncio
    async def test_slug_query_is_tried_first_and_costs_one_round_trip(self, db):
        """
        The tenant row's $id is not its slug, so the document-ID lookup always
        404s for this tenant and its only effect is latency. The slug query
        must answer on its own.
        """
        calls = []

        async def fake_request(method, path, params=None, **kwargs):
            calls.append(path)
            if path.endswith("/documents"):
                return {"documents": [{"$id": "68f0", "name": "Coal Creek", "config": "{}"}]}
            return None

        db._make_request = AsyncMock(side_effect=fake_request)

        config = await db.get_tenant_config("coalcreek")

        assert config["tenant_id"] == "coalcreek"
        assert config["business_name"] == "Coal Creek"
        assert len(calls) == 1, f"expected a single round trip, got {calls}"
        assert calls[0].endswith("/documents")

    @pytest.mark.asyncio
    async def test_falls_back_to_document_id_lookup(self, db):
        """
        A tenant whose row IS keyed by its id must still resolve — the slug
        query simply returns nothing for it.
        """
        calls = []

        async def fake_request(method, path, params=None, **kwargs):
            calls.append(path)
            if path.endswith("/documents"):
                return {"documents": []}
            return {"$id": "othertenant", "name": "Other Motel", "config": "{}"}

        db._make_request = AsyncMock(side_effect=fake_request)

        config = await db.get_tenant_config("othertenant")

        assert config["business_name"] == "Other Motel"
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_cache_hit_costs_no_round_trip(self, db):
        """The 5-minute cache is what keeps this off the hot path."""
        settings_module._tenant_config_cache["coalcreek"] = {
            "config": {"tenant_id": "coalcreek", "business_name": "Cached"},
            "ts": time.monotonic(),
        }
        db._make_request = AsyncMock()

        config = await db.get_tenant_config("coalcreek")

        assert config["business_name"] == "Cached"
        db._make_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_tenant_returns_empty_without_raising(self, db):
        """A voice call must survive a config miss rather than drop."""
        db._make_request = AsyncMock(return_value=None)

        assert await db.get_tenant_config("nope") == {}
