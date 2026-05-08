from __future__ import annotations

import pytest
import pytest_asyncio

from backend.application.contracts.intent import SlotBundle
from backend.application.graph.nodes.bootstrap_session import bootstrap_session


@pytest.mark.asyncio
async def test_bootstrap_creates_session_if_missing(fake_redis, monkeypatch):
    import backend.infrastructure.redis.session_store as ss

    monkeypatch.setattr(ss, "_pool", fake_redis)
    state = {"request_user_id": "u1", "request_session_id": None, "messages": []}
    out = await bootstrap_session(state)
    assert out["request_session_id"] is not None
    assert out["request_session_id"].startswith("s_")
    assert isinstance(out["accumulated_slots"], SlotBundle)
    assert out["clarify_count"] == 0


@pytest.mark.asyncio
async def test_bootstrap_restores_accumulated_slots(fake_redis, monkeypatch):
    import backend.infrastructure.redis.session_store as ss
    from backend.infrastructure.redis.session_store import save_slots

    monkeypatch.setattr(ss, "_pool", fake_redis)
    existing = SlotBundle(origin="BJS")
    await save_slots("s_existing", existing)

    state = {"request_user_id": "u1", "request_session_id": "s_existing", "messages": []}
    out = await bootstrap_session(state)
    assert out["accumulated_slots"].origin == "BJS"


@pytest.mark.asyncio
async def test_bootstrap_degrades_when_redis_unavailable(monkeypatch):
    import backend.infrastructure.redis.session_store as ss

    monkeypatch.setattr(ss, "_pool", None)
    state = {"request_user_id": "u1", "request_session_id": None, "messages": []}
    out = await bootstrap_session(state)
    assert out["request_session_id"].startswith("s_")
    assert isinstance(out["accumulated_slots"], SlotBundle)
