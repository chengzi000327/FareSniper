from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.__version__ import PRD_VERSION, PRODUCT_NAME, __version__
from backend.api.admin_intents import router as admin_intents_router
from backend.api.alerts import router as alerts_router
from backend.api.auth import router as auth_router
from backend.api.memory import router as memory_router
from backend.api.price_history import router as price_history_router
from backend.api.push_subscriptions import router as push_subscriptions_router
from backend.api.recommendations import router as recommendations_router
from backend.api.search import router as search_router
from backend.api.session import router as session_router
from backend.api.flight_status import router as flight_status_router
from backend.api.track import router as track_router
from backend.infrastructure.observability.latency_mw import record_latency
from backend.infrastructure.redis import session_store
from backend.api.track_jump import router as track_jump_router
from backend.application.graph.factory import get_graph
from backend.config import settings
from backend.workers.scheduler import build_scheduler
from backend.db.models import Base
from backend.schemas.common import HealthResponse
from backend.services.recommendation_service import RecommendationService

# Register dynamic intent tables before startup create_all runs.
import backend.infrastructure.db.intent_registry_repo  # noqa: F401,E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("faresniper.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── 启动：编译 graph、连接 PG/Redis ──────────────────
    graph = get_graph()
    app.state.graph = graph
    app.state.graph_compiled = graph is not None

    engine = (
        create_async_engine(settings.database_url, echo=False)
        if settings.database_url
        else None
    )
    redis_client = (
        aioredis.from_url(settings.redis_url, decode_responses=True)
        if settings.redis_url
        else None
    )
    session_store._pool = redis_client

    redis_ok = False
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_ok = True
        except Exception:
            logger.exception("redis_ping_failed")
            redis_ok = False

    if engine:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            logger.exception("database_init_failed")
            pass

    session_factory = (
        async_sessionmaker(engine, expire_on_commit=False) if engine else None
    )

    # ── 服务层 ────────────────────────────────────────────
    recommendation_service = RecommendationService(
        session_factory=session_factory,
        redis_client=redis_client,
    )

    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "app_startup graph_compiled=%s redis_ok=%s postgres_configured=%s scheduler_running=%s",
        app.state.graph_compiled,
        redis_ok,
        bool(engine),
        scheduler.running,
    )

    app.state.engine = engine
    app.state.redis_client = redis_client
    app.state.redis_ok = redis_ok
    app.state.session_factory = session_factory
    app.state.recommendation_service = recommendation_service
    app.state.scheduler = scheduler

    yield

    scheduler.shutdown(wait=False)

    if redis_client:
        try:
            await redis_client.aclose()
        except Exception:
            pass
    session_store._pool = None
    if engine:
        try:
            await engine.dispose()
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title=PRODUCT_NAME, version=__version__, lifespan=lifespan)

    def _custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=PRODUCT_NAME,
            version=__version__,
            routes=app.routes,
        )
        schema["info"]["x-prd-version"] = PRD_VERSION
        app.openapi_schema = schema
        return schema

    app.openapi = _custom_openapi  # type: ignore[method-assign]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(record_latency)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def healthcheck() -> HealthResponse:
        from sqlalchemy import text as sa_text

        pg_ok = False
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            try:
                async with engine.connect() as conn:
                    await conn.execute(sa_text("SELECT 1"))
                pg_ok = True
            except Exception:
                pass

        scheduler = getattr(app.state, "scheduler", None)
        scheduler_ok = scheduler is not None and getattr(scheduler, "running", False)

        langfuse_ok = bool(settings.langfuse_public_key)

        return HealthResponse(
            app=PRODUCT_NAME,
            graph_compiled=bool(getattr(app.state, "graph_compiled", False)),
            redis_ok=bool(getattr(app.state, "redis_ok", False)),
            postgres_ok=pg_ok,
            scheduler_ok=scheduler_ok,
            langfuse_ok=langfuse_ok,
        )

    app.include_router(session_router, prefix=settings.api_prefix)
    app.include_router(search_router, prefix=settings.api_prefix)
    app.include_router(memory_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    app.include_router(alerts_router, prefix=settings.api_prefix)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(price_history_router, prefix=settings.api_prefix)
    app.include_router(push_subscriptions_router, prefix=settings.api_prefix)
    app.include_router(track_jump_router, prefix=settings.api_prefix)
    app.include_router(track_router, prefix=settings.api_prefix)
    app.include_router(flight_status_router, prefix=settings.api_prefix)
    app.include_router(admin_intents_router, prefix=settings.api_prefix)

    return app


app = create_app()
