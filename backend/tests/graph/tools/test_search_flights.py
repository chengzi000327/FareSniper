from __future__ import annotations

import pytest

from backend.application.graph.tools.search_flights import search_flights


@pytest.mark.asyncio
async def test_returns_cached_when_available(seeded_pg_with_cache):
    out = await search_flights.ainvoke(
        {"origin": "BJS", "destination": "SHA", "depart_date": "2026-05-08"}
    )
    assert len(out["deals"]) >= 1
    assert out["source"] == "cache"


@pytest.mark.asyncio
async def test_realtime_fallback_when_cache_miss(seeded_pg_empty, stub_realtime):
    out = await search_flights.ainvoke(
        {"origin": "XIY", "destination": "URC", "depart_date": "2026-05-08"}
    )
    assert out["source"] == "realtime"


@pytest.mark.asyncio
async def test_mock_fallback_when_realtime_fails(seeded_pg_empty, monkeypatch):
    import backend.application.graph.tools.search_flights as sf

    async def _boom(*, origin, destination, depart_date):
        raise RuntimeError("browser unavailable")

    monkeypatch.setattr(sf, "scrape_realtime", _boom)

    out = await search_flights.ainvoke(
        {"origin": "BJS", "destination": "SHA", "depart_date": "2026-05-08"}
    )
    assert out["source"] == "mock_fallback"
    assert len(out["deals"]) >= 1
