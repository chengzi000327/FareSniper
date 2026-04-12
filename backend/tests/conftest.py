from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

# .env を backend/tests より 2 階層上の backend/.env から読む
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def tmp_memory_file(tmp_path: Path):
    original = settings.memory_file
    settings.memory_file = tmp_path / "memory.json"
    yield settings.memory_file
    settings.memory_file = original


@pytest_asyncio.fixture
async def client(tmp_memory_file: Path) -> AsyncGenerator[AsyncClient, None]:
    from asgi_lifespan import LifespanManager
    from backend.main import create_app

    app = create_app()
    async with LifespanManager(app, startup_timeout=30) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.database_url, echo=False)
    yield engine
    try:
        await engine.dispose()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="session")
async def redis_client():
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    yield client
    try:
        await client.aclose()
    except Exception:
        pass
