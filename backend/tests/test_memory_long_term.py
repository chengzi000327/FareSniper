"""
Step 4 长期记忆测试 — Railway PostgreSQL
preferences / query_history / click_history CRUD
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.memory.long_term import LongTermMemory

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def db_engine():
    engine = create_async_engine(settings.database_url, echo=False)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest_asyncio.fixture(loop_scope="module")
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass


@pytest.fixture
def ltm(db_session: AsyncSession):
    return LongTermMemory(db_session)


async def test_upsert_and_get_preferences(ltm: LongTermMemory):
    """upsert 偏好 → get 能读到，字段正确。"""
    await ltm.upsert_preferences("ltm-test-user", {
        "budget": 4000,
        "frequent_cities": ["东京"],
        "preferred_airlines": ["中国国航"],
        "constraints": ["avoid_redeye"],
        "travel_scenes": ["holiday"],
    })

    pref = await ltm.get_preferences("ltm-test-user")
    assert pref is not None
    assert pref["budget"] == 4000
    assert "东京" in pref["frequent_cities"]
    assert "中国国航" in pref["preferred_airlines"]
    assert "avoid_redeye" in pref["constraints"]
    assert "holiday" in pref["travel_scenes"]


async def test_upsert_is_idempotent(ltm: LongTermMemory):
    """第二次 upsert 更新字段，不新增行。"""
    await ltm.upsert_preferences("ltm-test-user", {"budget": 3000})
    await ltm.upsert_preferences("ltm-test-user", {"budget": 5000})

    pref = await ltm.get_preferences("ltm-test-user")
    assert pref["budget"] == 5000


async def test_add_query_history(ltm: LongTermMemory):
    """add_query 写入一条记录，get_recent_queries 能读到。"""
    await ltm.add_query("ltm-test-user", "北京到东京", intent={"origin": "PEK", "destination": "NRT"})

    queries = await ltm.get_recent_queries("ltm-test-user", limit=5)
    assert len(queries) >= 1
    assert any(q["query_text"] == "北京到东京" for q in queries)


async def test_add_click_history(ltm: LongTermMemory):
    """add_click 写入一条点击记录，get_recent_clicks 能读到 flight_data。"""
    flight = {"flight_no": "CA901", "price": 2580, "origin": "PEK", "destination": "NRT"}
    await ltm.add_click("ltm-test-user", flight)

    clicks = await ltm.get_recent_clicks("ltm-test-user", limit=5)
    assert len(clicks) >= 1
    assert any(c["flight_data"]["flight_no"] == "CA901" for c in clicks)


async def test_get_preferences_none_for_new_user(ltm: LongTermMemory):
    """未知用户 get_preferences 返回 None。"""
    pref = await ltm.get_preferences("no-such-user-xyz")
    assert pref is None
