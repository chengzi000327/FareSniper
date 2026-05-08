import pytest
from backend.application.services import recommendation_service as svc


@pytest.mark.asyncio
async def test_second_call_skips_db(seeded_pg, fake_redis, monkeypatch):
    """缓存命中时不应再走 DB；用 spy 计数 _build_recommendations_uncached 的调用次数。"""
    import backend.infrastructure.redis.session_store as ss

    monkeypatch.setattr(ss, "_pool", fake_redis)

    calls = {"n": 0}
    real = svc._build_recommendations_uncached

    async def spy(uid):
        calls["n"] += 1
        return await real(uid)

    monkeypatch.setattr(svc, "_build_recommendations_uncached", spy)

    await svc.build_recommendations("u1")
    await svc.build_recommendations("u1")
    assert calls["n"] == 1, "second call should hit redis cache, not DB"


@pytest.mark.asyncio
async def test_different_user_breaks_cache(seeded_pg, fake_redis, monkeypatch):
    import backend.infrastructure.redis.session_store as ss

    monkeypatch.setattr(ss, "_pool", fake_redis)

    calls = {"n": 0}
    real = svc._build_recommendations_uncached

    async def spy(uid):
        calls["n"] += 1
        return await real(uid)

    monkeypatch.setattr(svc, "_build_recommendations_uncached", spy)

    await svc.build_recommendations("u_a")
    await svc.build_recommendations("u_b")
    assert calls["n"] == 2
