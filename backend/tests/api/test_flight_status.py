import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
def stub_flight_status_api(monkeypatch):
    import backend.api.flight_status as api_fs

    async def _fake_fetch(flight_no: str, date: str) -> dict:
        return {"flight_no": flight_no, "date": date, "status": "on_time", "delay_minutes": 0}

    monkeypatch.setattr(api_fs, "fetch_status", _fake_fetch)


@pytest.mark.asyncio
async def test_get_status(stub_flight_status_api):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/flight_status", params={"flight_no": "MU5137", "date": "2026-05-08"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"on_time", "delayed", "cancelled"}
