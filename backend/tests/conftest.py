from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles

# .env を backend/tests より 2 階層上の backend/.env から読む
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.config import settings  # noqa: E402


# ── PG-only column types compiled to SQLite-compatible JSON for seeded_pg ──
@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(_type, _compiler, **_kw):
    return "JSON"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from asgi_lifespan import LifespanManager
    from backend.main import create_app

    app = create_app()
    async with LifespanManager(app, startup_timeout=30) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(settings.database_url, echo=False)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest_asyncio.fixture
async def redis_client():
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield client
    try:
        await client.aclose()
    except Exception:
        pass


@pytest_asyncio.fixture
async def seeded_pg():
    """Isolated SQLite-in-memory engine bound into ``infrastructure.db.base``.

    Rebinds the canonical ``engine`` / ``SessionLocal`` symbols on
    ``backend.infrastructure.db.base`` for the duration of the test so any
    repo module that does ``from backend.infrastructure.db.base import ...``
    transparently uses the throwaway SQLite database. Existing tables in
    ``backend.db.models`` are created up-front.

    Scenario fixtures (`seeded_pg_with_*`) and the `enable_flag` helper from
    the original plan are intentionally NOT defined here — they will land in
    the TG that introduces their backing repo modules.
    """
    from backend.infrastructure.db import base as db_base

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", future=True
    )
    test_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )

    saved_engine = db_base.engine
    saved_session = db_base.SessionLocal
    db_base.engine = test_engine
    db_base.SessionLocal = test_session_factory

    async with test_engine.begin() as conn:
        await conn.run_sync(db_base.Base.metadata.create_all)

    try:
        yield test_engine
    finally:
        db_base.engine = saved_engine
        db_base.SessionLocal = saved_session
        await test_engine.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    """In-process FakeRedis instance.

    Tests that need ``backend.infrastructure.redis.session_store`` to use
    this fake should monkeypatch it themselves once that module is created
    in a later TG. Returning a bare instance here keeps the fixture usable
    for any code path that simply needs a Redis-shaped object.
    """
    from backend.tests._fakes.redis import FakeRedis

    fake = FakeRedis()
    try:
        yield fake
    finally:
        await fake.close()
