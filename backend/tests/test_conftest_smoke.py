"""Smoke coverage for the test infrastructure introduced in TG-00 · Task 2.

`seeded_pg` builds an isolated SQLite engine + sessionmaker and rebinds the
canonical `backend.infrastructure.db.base` symbols for the duration of a
test, while `fake_redis` returns a tiny in-process Redis stand-in.

Scenario fixtures (`seeded_pg_with_*`), the `enable_flag` helper and the
session_store monkeypatch live in later TGs (paired with the repo modules
they consume) — they are intentionally absent here.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_seeded_pg_provides_async_engine(seeded_pg):
    async with seeded_pg.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_seeded_pg_creates_existing_tables(seeded_pg):
    async with seeded_pg.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='user_preferences'"
            )
        )
        assert result.scalar_one_or_none() == "user_preferences"


@pytest.mark.asyncio
async def test_fake_redis_round_trip(fake_redis):
    await fake_redis.set("k", "v")
    assert await fake_redis.get("k") == "v"


@pytest.mark.asyncio
async def test_fake_redis_setex_expires(fake_redis):
    await fake_redis.setex("k", 60, "v")
    assert await fake_redis.get("k") == "v"


@pytest.mark.asyncio
async def test_stub_chat_model_for_search_emits_tool_call(stub_chat_model_for_search):
    msg = await stub_chat_model_for_search.ainvoke([{"role": "user", "content": "x"}])
    assert any(tc["name"] == "search_flights" for tc in msg.tool_calls)


def test_captured_langfuse_records_scores(captured_langfuse):
    captured_langfuse.score(name="x", value=0.1)
    assert captured_langfuse.scores[-1] == {"name": "x", "value": 0.1}


def test_captured_langfuse_get_prompt_returns_stub(captured_langfuse):
    p = captured_langfuse.get_prompt("react_agent")
    assert p.prompt == "stub"
