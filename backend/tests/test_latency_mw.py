import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.infrastructure.db.event_repo import count_events
from backend.analytics.events import EventName


@pytest.mark.asyncio
async def test_latency_header_set_on_every_response(seeded_pg):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert "x-latency-ms" in r.headers
    assert int(r.headers["x-latency-ms"]) >= 0


@pytest.mark.asyncio
async def test_latency_does_not_emit_business_events(seeded_pg):
    """中间件只设 header，不写 result_viewed。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/health")
    n = await count_events(EventName.RESULT_VIEWED, user_id="anon_unknown")
    assert n == 0
