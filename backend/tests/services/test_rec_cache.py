import json

import pytest

from backend.application.contracts.recommendations import RecCard
from backend.application.services import recommendation_service as svc


@pytest.mark.asyncio
async def test_second_call_reuses_the_shared_card_pool(fake_redis, monkeypatch):
    build_calls = 0

    async def build_pool():
        nonlocal build_calls
        build_calls += 1
        return [RecCard(id="shared", title="北京→上海", reason="监控中")]

    async def identity_personalize(user_id, pool):
        return list(pool), False

    monkeypatch.setattr(svc, "_redis", lambda: fake_redis)
    monkeypatch.setattr(svc, "_build_card_pool", build_pool)
    monkeypatch.setattr(svc, "_personalize", identity_personalize)

    await svc.build_recommendations("u1")
    await svc.build_recommendations("u1")

    assert build_calls == 1
    raw = await fake_redis.get(svc.POOL_CACHE_KEY)
    envelope = json.loads(raw or "null")
    assert envelope["version"] == svc.POOL_CACHE_ENVELOPE_VERSION
    assert envelope["cards"][0]["id"] == "shared"


@pytest.mark.asyncio
async def test_different_users_share_build_but_personalize_separately(
    fake_redis,
    monkeypatch,
):
    build_calls = 0
    personalized_users = []

    async def build_pool():
        nonlocal build_calls
        build_calls += 1
        return [RecCard(id="shared", title="北京→上海", reason="监控中")]

    async def capture_personalize(user_id, pool):
        personalized_users.append(user_id)
        return list(pool), False

    monkeypatch.setattr(svc, "_redis", lambda: fake_redis)
    monkeypatch.setattr(svc, "_build_card_pool", build_pool)
    monkeypatch.setattr(svc, "_personalize", capture_personalize)

    await svc.build_recommendations("u_a")
    await svc.build_recommendations("u_b")

    assert build_calls == 1
    assert personalized_users == ["u_a", "u_b"]
