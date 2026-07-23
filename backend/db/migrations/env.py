from __future__ import annotations

import asyncio
import importlib
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# 把项目根（FareSniper/）加到 sys.path，让 `import backend` 可用
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 加载 .env（alembic 直接运行时不经过 conftest）
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from backend.config import settings  # noqa: E402
from backend.infrastructure.db.base import Base  # noqa: E402

# 让所有 canonical schema 表都注册到 Base.metadata。
# 各 repo 模块由后续 TG 增量补齐；尚未存在的模块本身会被静默跳过，
# 但模块内部的 import 错误必须暴露出来，避免被吞。
_REPO_MODULES = [
    "backend.infrastructure.db.event_repo",
    "backend.infrastructure.db.feature_flag_repo",
    "backend.infrastructure.db.cps_settlement_repo",
    "backend.infrastructure.db.flight_cache",
    "backend.infrastructure.db.flight_snapshot_repo",
    "backend.infrastructure.db.flight_demand_repo",
    "backend.infrastructure.db.memory_repo",
    "backend.infrastructure.db.query_history_repo",
    "backend.infrastructure.db.user_repo",
    "backend.infrastructure.db.alert_repo",
    "backend.infrastructure.db.wechat_repo",
    "backend.infrastructure.db.notification_repo",
    "backend.infrastructure.db.push_subscription_repo",
    "backend.infrastructure.db.price_history_repo",
    "backend.infrastructure.db.promotion_repo",
    "backend.infrastructure.db.session_meta_repo",
    "backend.infrastructure.db.intent_registry_repo",
]
for mod in _REPO_MODULES:
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError as exc:
        if exc.name != mod:
            # 目标模块本身存在，但内部 import 失败：必须抛出
            raise

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: context.configure(
                connection=c,
                target_metadata=target_metadata,
                render_as_batch=c.dialect.name == "sqlite",
            )
        )
        await conn.run_sync(lambda _: context.run_migrations())
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
