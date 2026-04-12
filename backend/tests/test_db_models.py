"""
Step 2 数据库模型测试
Railway PostgreSQL — 验证 4 张表的 CRUD 和字段约束。
每个测试后 rollback，不污染数据库。
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.models import ChatHistory, ClickHistory, QueryHistory, UserPreference


@pytest.fixture
async def db_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        try:
            await session.rollback()
        except Exception:
            pass
    try:
        await engine.dispose()
    except Exception:
        pass


async def test_user_preference_crud(db_session: AsyncSession):
    """UserPreference 创建 → 读取 → 验证字段完整。"""
    pref = UserPreference(
        id="test-user-1",
        price_anchor=3000,
        preferred_origins=["PEK", "SHA"],
        preferred_destinations=["NRT", "ICN"],
        cabin_preference="economy",
        extra={"theme": "dark"},
    )
    db_session.add(pref)
    await db_session.flush()

    fetched = await db_session.get(UserPreference, "test-user-1")
    assert fetched is not None
    assert fetched.price_anchor == 3000
    assert "PEK" in fetched.preferred_origins
    assert fetched.cabin_preference == "economy"
    assert fetched.extra["theme"] == "dark"
    assert fetched.updated_at is not None


async def test_query_history_created_at(db_session: AsyncSession):
    """QueryHistory 创建后 created_at 自动填充。"""
    record = QueryHistory(
        user_id="test-user-1",
        query_text="北京到东京最便宜的机票",
        intent={"origin": "PEK", "destination": "NRT"},
    )
    db_session.add(record)
    await db_session.flush()

    assert record.id is not None
    assert record.created_at is not None
    assert record.intent["origin"] == "PEK"


async def test_click_history_jsonb(db_session: AsyncSession):
    """ClickHistory flight_data JSONB 字段可存取复杂结构。"""
    flight = {
        "flight_no": "CA901",
        "origin": "PEK",
        "destination": "NRT",
        "price": 2580,
        "segments": [{"dep": "PEK", "arr": "NRT"}],
    }
    record = ClickHistory(user_id="test-user-1", flight_data=flight)
    db_session.add(record)
    await db_session.flush()

    assert record.id is not None
    assert record.flight_data["flight_no"] == "CA901"
    assert record.flight_data["segments"][0]["dep"] == "PEK"
    assert record.clicked_at is not None


async def test_chat_history_messages(db_session: AsyncSession):
    """ChatHistory 多条消息读写，session_id 和 role 正确存储。"""
    messages = [
        ChatHistory(user_id="test-user-1", session_id="sess-abc", role="user", content="帮我找机票"),
        ChatHistory(user_id="test-user-1", session_id="sess-abc", role="assistant", content="好的，请问出发地？"),
    ]
    for msg in messages:
        db_session.add(msg)
    await db_session.flush()

    for msg in messages:
        assert msg.id is not None
        assert msg.created_at is not None

    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[1].content == "好的，请问出发地？"
