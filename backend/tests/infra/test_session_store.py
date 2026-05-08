from __future__ import annotations

import pytest

from backend.application.contracts.intent import SlotBundle
from backend.infrastructure.redis.session_store import (
    close_redis,
    init_redis,
    load_slots,
    save_slots,
)


@pytest.mark.asyncio
async def test_save_then_load(fake_redis, monkeypatch):
    import backend.infrastructure.redis.session_store as ss

    monkeypatch.setattr(ss, "_pool", fake_redis)
    await save_slots("s_test", SlotBundle(origin="BJS"))
    out = await load_slots("s_test")
    assert out is not None
    assert out.origin == "BJS"
