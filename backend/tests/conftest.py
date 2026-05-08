from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator, Optional

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# .env を backend/tests より 2 階層上の backend/.env から読む
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Tests must always have a non-trivial JWT secret so HMAC-SHA256 doesn't
# emit a 0-byte-key warning. setdefault preserves any prod value already
# present in .env.
os.environ.setdefault(
    "JWT_SECRET", "faresniper-test-only-secret-not-for-production-use"
)

from backend.config import settings  # noqa: E402


def _require_test_database_url() -> str:
    if not settings.test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not configured. Provision a Railway test PG "
            "service (separate from prod), set the +asyncpg DSN in backend/.env, "
            "and never reuse DATABASE_URL — tests will pollute production data."
        )
    if settings.test_database_url == settings.database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must point at a DIFFERENT database than "
            "DATABASE_URL. Provision a dedicated Railway test PG."
        )
    return settings.test_database_url


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
    """Engine connected to the **test** PG (never prod).

    Existing call sites that use ``db_engine`` were originally targeting the
    prod database; we rerouted them at the same time we introduced this
    fixture, so tests cannot accidentally read or write live data. If you
    truly need to query prod, instantiate an engine explicitly with
    ``settings.database_url``.
    """
    engine = create_async_engine(_require_test_database_url(), echo=False)
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


# Tables wiped between tests. Order matters only if FKs cascade — TRUNCATE
# ... CASCADE handles the rest.
_TRUNCATE_TARGETS = [
    "analytics_events",
    "click_history",
    "chat_history",
    "query_history",
    "user_preferences",
    "price_alerts",
    "sessions",
]


async def _truncate_all(engine) -> None:
    """Empty every test-PG table without dropping schema or views."""
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
            )
        )
        tables = [row[0] for row in rows]
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def seeded_pg():
    """Isolated PG engine bound into ``infrastructure.db.base``.

    Connects to the dedicated Railway test PG (``settings.test_database_url``).
    The schema must already be at alembic head — bootstrap it once with
    ``DATABASE_URL=$TEST_DATABASE_URL alembic -c backend/alembic.ini upgrade head``.
    Each test starts with every table truncated, but the schema itself
    (tables, indexes, views, constraints) stays intact, so PG-only views
    such as ``v_monthly_qpc`` are queryable.
    """
    from backend.infrastructure.db import base as db_base

    test_engine = create_async_engine(_require_test_database_url(), future=True)
    test_session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )

    saved_engine = db_base.engine
    saved_session = db_base.SessionLocal
    db_base.engine = test_engine
    db_base.SessionLocal = test_session_factory

    await _truncate_all(test_engine)

    try:
        yield test_engine
    finally:
        db_base.engine = saved_engine
        db_base.SessionLocal = saved_session
        await test_engine.dispose()


@pytest_asyncio.fixture
async def enable_flag(seeded_pg):
    """Convenience helper to flip a feature flag inside a test.

    Yields ``await enable_flag(name, rollout_pct=100)``. Hidden behind a
    ``seeded_pg`` dependency so the truncate runs first; otherwise prod
    seed rows would survive into the test scope.
    """
    from backend.infrastructure.db.feature_flag_repo import set_flag

    async def _enable(name: str, *, rollout_pct: int = 100) -> None:
        await set_flag(name, True, rollout_pct=rollout_pct)

    return _enable


@pytest_asyncio.fixture
async def seeded_pg_with_events(seeded_pg):
    """Pre-populates analytics_events with mixed deeplink_ok / latency rows.

    Used by guardrail tests that need a real PG path through FILTER and
    percentile_cont. The rows are crafted so ``deeplink_failure_rate``
    crosses the 5% threshold — 16 of 20 events have ``deeplink_ok=false``.
    """
    from backend.analytics.events import EventName
    from backend.analytics.track import track

    payloads = []
    for i in range(20):
        payloads.append(
            {
                "flight_no": f"MU{5000 + i}",
                "platform": "ctrip",
                "price": 480 + i,
                "deeplink_ok": "false" if i < 16 else "true",
                "misleading": "true" if i < 1 else "false",
                "latency_ms": 1500 + i * 50,
            }
        )
    for payload in payloads:
        await track(EventName.PURCHASE_JUMPED, user_id="u1", payload=payload)
    return seeded_pg


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


class _StubChatModel:
    """Minimal LangChain-shaped chat model returning a canned AIMessage.

    Production wiring will plug this into ``backend.infrastructure.llm.models``
    once the ``build_chat_model(role)`` factory exists. For now the stub is
    self-contained — tests that need to bypass LLM calls can request the
    fixtures below.
    """

    def __init__(
        self,
        tool_calls: Optional[list[dict]] = None,
        content: str = "",
    ) -> None:
        self._tool_calls = tool_calls or []
        self._content = content
        self.model = "stub-chat"

    def bind_tools(self, _tools):
        return self

    def with_config(self, _cfg):
        return self

    async def ainvoke(self, _messages):
        return AIMessage(content=self._content, tool_calls=self._tool_calls)


@pytest.fixture
def stub_chat_model_for_search() -> _StubChatModel:
    return _StubChatModel(
        tool_calls=[
            {
                "id": "c1",
                "name": "search_flights",
                "args": {
                    "origin": "BJS",
                    "destination": "SHA",
                    "depart_date": "2026-05-08",
                },
            }
        ]
    )


@pytest.fixture
def stub_chat_judge_buy_now() -> _StubChatModel:
    return _StubChatModel(
        content='{"verdict":"buy_now","advice":"历史低价建议尽快下单","signals":["历史低价"]}'
    )


@pytest.fixture
def captured_langfuse():
    from backend.tests._fakes.langfuse import CapturedLangfuse

    return CapturedLangfuse()


def _mint_jwt(sub: str) -> str:
    """Helper for tests that need a valid Bearer token."""
    import jwt as _jwt

    return _jwt.encode(
        {"sub": sub}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


@pytest.fixture
def valid_jwt_for_u1() -> str:
    return _mint_jwt("u1")


@pytest.fixture
def jwt_for():
    """Yield a factory that mints a Bearer JWT for any user_id."""
    return _mint_jwt


class _FakePush:
    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, user_id: str, title: str, body: str, subscription: dict):
        self.calls.append(
            {"user_id": user_id, "title": title, "body": body, "sub": subscription}
        )


@pytest.fixture
def fake_push(monkeypatch):
    import backend.workers.push_dispatcher as pd

    fp = _FakePush()
    monkeypatch.setattr(pd, "send_push", fp.send)
    try:
        import backend.workers.alert_checker as ac

        monkeypatch.setattr(ac, "send_push", fp.send)
    except ImportError:
        pass
    return fp


@pytest_asyncio.fixture
async def seeded_pg_with_low_price(seeded_pg):
    """seeded_pg with a BJS→SYX deal at price=300 in flight_cache."""
    from backend.infrastructure.db.flight_cache import write_cached_deals

    await write_cached_deals(
        origin="BJS",
        destination="SYX",
        depart_date="2026-05-01",
        deals=[{"flight_no": "MU001", "price": 300, "platform": "ctrip"}],
    )
    return seeded_pg


@pytest_asyncio.fixture
async def seeded_pg_with_memory(seeded_pg):
    """seeded_pg with u1's budget_ceiling=500 pre-loaded in memories."""
    from backend.infrastructure.db.memory_repo import upsert_memory

    await upsert_memory("u1", "budget_ceiling", 500, source="user")
    return seeded_pg


@pytest_asyncio.fixture
async def seeded_pg_with_cache(seeded_pg):
    """seeded_pg with one BJS→SHA deal pre-loaded in flight_cache."""
    from backend.infrastructure.db.flight_cache import write_cached_deals

    await write_cached_deals(
        origin="BJS",
        destination="SHA",
        depart_date="2026-05-08",
        deals=[{"flight_no": "MU5137", "price": 480, "platform": "ctrip"}],
    )
    return seeded_pg


@pytest_asyncio.fixture
async def seeded_pg_empty(seeded_pg):
    """seeded_pg with no flight_cache rows — forces realtime fallback."""
    return seeded_pg


@pytest.fixture
def stub_realtime(monkeypatch):
    """Replace scrape_realtime with a deterministic stub returning one deal."""
    import backend.infrastructure.scrapers.realtime_fallback as rf

    async def _stub(*, origin, destination, depart_date):
        return [{"flight_no": "XX001", "price": 300, "platform": "stub"}]

    monkeypatch.setattr(rf, "scrape_realtime", _stub)
    # Also patch through to the tool module if it was already imported
    try:
        import backend.application.graph.tools.search_flights as sf

        monkeypatch.setattr(sf, "scrape_realtime", _stub)
    except ImportError:
        pass


@pytest.fixture
def stub_playwright(monkeypatch):
    """Replace _launch_browser with a FakeBrowser so scrapers never start Chromium.

    FakeBrowser.new_page().content() returns '<html></html>', which causes each
    scraper's _parse() to take the deterministic placeholder branch and tag
    every deal with source='fake'.  multi_platform.scrape_all_routes then
    refuses to write those into flight_cache.
    """
    import backend.infrastructure.scrapers.base_scraper as bs

    class _FakeBrowser:
        class _FakePage:
            async def goto(self, url: str, **kwargs) -> None:
                pass

            async def wait_for_selector(self, selector: str, **kwargs) -> None:
                pass

            async def content(self) -> str:
                return "<html></html>"

        async def new_page(self):
            return self._FakePage()

        async def close(self) -> None:
            pass

    async def _fake_launch():
        return _FakeBrowser()

    monkeypatch.setattr(bs, "_browser_factory", _fake_launch)
