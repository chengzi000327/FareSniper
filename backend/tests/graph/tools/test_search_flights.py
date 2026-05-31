from __future__ import annotations

import pytest

from backend.application.graph.tools.search_flights import search_flights


@pytest.mark.asyncio
async def test_returns_snapshot_cache_when_available(seeded_pg):
    from backend.infrastructure.db.flight_snapshot_repo import upsert_flights

    await upsert_flights(
        [
            {
                "flight_no": "MU5137",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2026-05-08",
                "dep_time": "08:30",
                "arr_time": "11:00",
                "duration": "2h30m",
                "stops": 0,
                "lowest_price": 480,
                "history_avg_90d": None,
                "history_low_90d": None,
                "prices": [{"platform": "ctrip", "price": 480, "lowest": True, "url": ""}],
            }
        ]
    )

    out = await search_flights.ainvoke(
        {"origin": "BJS", "destination": "SHA", "depart_date": "2026-05-08"}
    )
    assert len(out["deals"]) >= 1
    assert out["source"] == "cache"
    assert out["deals"][0]["prices"][0]["platform"] == "ctrip"


@pytest.mark.asyncio
async def test_variflight_fallback_when_cache_miss(seeded_pg_empty, stub_realtime):
    out = await search_flights.ainvoke(
        {"origin": "XIY", "destination": "URC", "depart_date": "2026-05-08"}
    )
    assert out["source"] == "variflight"


@pytest.mark.asyncio
async def test_mock_fallback_when_variflight_fails(seeded_pg_empty, monkeypatch):
    import backend.application.graph.tools.search_flights as sf

    async def _boom(origin, destination, depart_date):
        raise RuntimeError("variflight unavailable")

    monkeypatch.setattr(sf, "variflight_search", _boom)

    out = await search_flights.ainvoke(
        {"origin": "BJS", "destination": "SHA", "depart_date": "2026-05-08"}
    )
    assert out["source"] == "mock_fallback"
    assert len(out["deals"]) >= 1
