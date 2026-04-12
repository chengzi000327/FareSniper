from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# 把项目根（FareSniper/）加到 sys.path，让 `import backend` 可用
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# 加载 .env（alembic 直接运行时不经过 conftest）
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from backend.config import settings  # noqa: E402
from backend.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: context.configure(connection=c, target_metadata=target_metadata)
        )
        await conn.run_sync(lambda _: context.run_migrations())
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
