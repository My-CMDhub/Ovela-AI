import httpx
import pytest
from main import app

@pytest.mark.asyncio
async def test_tenant_settings_coalcreek():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/dashboard/settings?tenant_id=coalcreek")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["settings"]["business_name"] == "Coal Creek Motel"

@pytest.mark.asyncio
async def test_tenant_settings_fallback_to_coalcreek():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/dashboard/settings?tenant_id=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["settings"]["business_name"] == "Coal Creek Motel"

