from __future__ import annotations

import pytest

from backend.infrastructure.resilience.retry import with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_after_2_failures():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    out = await with_retry(flaky, attempts=3, base_delay=0.001)
    assert out == "ok"
    assert calls["n"] == 3
