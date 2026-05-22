import httpx
import pytest
from main import app

@pytest.mark.asyncio
async def test_active_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "Ovela AI Backend is running" in response.json()["message"]

@pytest.mark.asyncio
async def test_purged_routes():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhooks/meta")
        assert response.status_code == 404
