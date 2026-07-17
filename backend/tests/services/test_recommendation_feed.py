"""探索页瀑布流 feed 升级测试:分页 / 折扣分级 / 缓存分层 / booking 深链。

全部走 TEST_DATABASE_URL(seeded_pg fixture),并把 session_store._redis
打成内存 FakeRedis,验证 L1 全局卡片池缓存与 L2 个性化排序。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import backend.application.services.recommendation_service as svc
from backend.application.contracts.recommendations import RecCard
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights


def _flight(
    dest: str,
    price: int,
    fno: str,
    *,
    depart_date: str | None = None,
    history_avg_90d: int | None = None,
    history_low_90d: int | None = None,
    platform: str = "ctrip",
) -> dict:
    effective_date = depart_date or (
        datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    ).isoformat()
    return {
        "flight_no": fno,
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": dest,
        "depart_date": effective_date,
        "currency": "CNY",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "2h",
        "stops": 0,
        "lowest_price": price,
        "history_avg_90d": history_avg_90d,
        "history_low_90d": history_low_90d,
        "prices": [{"platform": platform, "price": price, "currency": "CNY", "lowest": True, "url": ""}],
    }


@pytest.fixture
def patched_redis(fake_redis, monkeypatch):
    """把推荐服务读到的 _redis() 换成内存 FakeRedis。"""
    monkeypatch.setattr(svc, "_redis", lambda: fake_redis)
    return fake_redis


def _patch_renderable_pool(monkeypatch) -> None:
    cards = [
        RecCard(
            id=f"card-{destination}",
            title=(
                f"{svc.CITY_NAMES.get(origin, origin)}→"
                f"{svc.CITY_NAMES.get(destination, destination)}"
            ),
            reason="future inventory",
            preview_deal={"depart_date": "2099-08-01"},
        )
        for origin, destination in svc.HOT_ROUTES
    ]

    async def fake_pool():
        return cards

    monkeypatch.setattr(svc, "_get_card_pool", fake_pool)


# ── 分页 ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_first_page_has_more(
    seeded_pg, patched_redis, monkeypatch
):
    _patch_renderable_pool(monkeypatch)
    rsp = await svc.build_recommendations("anon-page", limit=6, offset=0)
    assert len(rsp.cards) == 6
    # 路线池有 14 条 → 还有下一页
    assert rsp.has_more is True
    assert rsp.next_offset == 6


@pytest.mark.asyncio
async def test_pagination_offset_slices(
    seeded_pg, patched_redis, monkeypatch
):
    _patch_renderable_pool(monkeypatch)
    page1 = await svc.build_recommendations("anon-page", limit=6, offset=0)
    page2 = await svc.build_recommendations("anon-page", limit=6, offset=6)
    ids1 = {c.title for c in page1.cards}
    ids2 = {c.title for c in page2.cards}
    assert ids1.isdisjoint(ids2)  # 两页不重叠


@pytest.mark.asyncio
async def test_pagination_last_page_no_more(
    seeded_pg, patched_redis, monkeypatch
):
    _patch_renderable_pool(monkeypatch)
    rsp = await svc.build_recommendations("anon-page", limit=6, offset=12)
    assert rsp.has_more is False
    assert len(rsp.cards) <= 6


# ── 折扣分级 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discount_prefers_history_avg(seeded_pg, patched_redis):
    # history_avg_90d=500, price=300 → 折扣 40%(优先级最高)
    await upsert_flights([
        _flight("SHA", 300, "MU1", history_avg_90d=500),
        _flight("SHA", 600, "MU2", history_avg_90d=500),
        _flight("SHA", 700, "MU3", history_avg_90d=500),
    ])
    rsp = await svc.build_recommendations("anon-disc", limit=15, offset=0)
    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.discount_pct == 40


@pytest.mark.asyncio
async def test_discount_null_when_sample_too_small(seeded_pg, patched_redis):
    # 只有 2 条且无 history_avg → 样本<3,折扣返 null
    await upsert_flights([
        _flight("SHA", 300, "MU1"),
        _flight("SHA", 600, "MU2"),
    ])
    rsp = await svc.build_recommendations("anon-disc2", limit=15, offset=0)
    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.discount_pct is None


@pytest.mark.asyncio
async def test_discount_capped_at_50(seeded_pg, patched_redis):
    await upsert_flights([
        _flight("SHA", 100, "MU1", history_avg_90d=1000),
        _flight("SHA", 900, "MU2", history_avg_90d=1000),
        _flight("SHA", 950, "MU3", history_avg_90d=1000),
    ])
    rsp = await svc.build_recommendations("anon-cap", limit=15, offset=0)
    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.discount_pct == 50


@pytest.mark.asyncio
async def test_history_low_signal(seeded_pg, patched_redis):
    # price 触及 history_low_90d → "历史低价" 信号
    await upsert_flights([
        _flight("SHA", 280, "MU1", history_avg_90d=500, history_low_90d=280),
        _flight("SHA", 600, "MU2", history_avg_90d=500, history_low_90d=280),
        _flight("SHA", 650, "MU3", history_avg_90d=500, history_low_90d=280),
    ])
    rsp = await svc.build_recommendations("anon-low", limit=15, offset=0)
    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.preview_deal is not None
    assert "历史低价" in sha.preview_deal["signals"]


# ── booking 深链 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_booking_url_written(seeded_pg, patched_redis):
    await upsert_flights([
        _flight("SHA", 280, "MU1", history_avg_90d=500, platform="ctrip"),
        _flight("SHA", 600, "MU2", history_avg_90d=500, platform="ctrip"),
        _flight("SHA", 650, "MU3", history_avg_90d=500, platform="ctrip"),
    ])
    rsp = await svc.build_recommendations("anon-book", limit=15, offset=0)
    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.preview_deal is not None
    url = sha.preview_deal.get("booking_url")
    assert url and url.startswith("http")
    assert "MU1" in url  # 最低价航班深链


# ── 缓存分层 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l1_pool_shared_across_users(seeded_pg, patched_redis):
    await svc.build_recommendations("user-A", limit=6, offset=0)
    # L1 池应已写入,key=rec:pool:v1
    assert await patched_redis.get(svc.POOL_CACHE_KEY) is not None


@pytest.mark.asyncio
async def test_l2_personalization_moves_preferred_first(
    seeded_pg, patched_redis, monkeypatch
):
    _patch_renderable_pool(monkeypatch)
    from backend.infrastructure.db.base import get_session
    from backend.memory.long_term import LongTermMemory

    async with get_session() as db:
        await LongTermMemory(db).upsert_preferences("u-pref", {"frequent_cities": ["哈尔滨"]})
        await db.commit()

    rsp = await svc.build_recommendations("u-pref", limit=6, offset=0)
    # 哈尔滨应被提前到首页且打 "符合偏好" 标签
    titles = [c.title for c in rsp.cards]
    assert any(t.endswith("哈尔滨") for t in titles)
    hrb = next(c for c in rsp.cards if c.title.endswith("哈尔滨"))
    assert "符合偏好" in hrb.tags
    assert rsp.personalized is True
