from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.__version__ import PRD_VERSION, PRODUCT_NAME, __version__
from backend.api.alerts import router as alerts_router
from backend.api.memory import router as memory_router
from backend.api.recommendations import router as recommendations_router
from backend.api.search import router as search_router
from backend.api.session import router as session_router
from backend.config import settings
from backend.db.models import Base
from backend.schemas.common import HealthResponse
from backend.services.recommendation_service import RecommendationService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── 启动：初始化基础设施 ──────────────────────────────
    engine = create_async_engine(settings.database_url, echo=False) if settings.database_url else None
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None

    if engine:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            pass

    session_factory = async_sessionmaker(engine, expire_on_commit=False) if engine else None

    # ── 服务层 ────────────────────────────────────────────
    recommendation_service = RecommendationService(
        session_factory=session_factory,
        redis_client=redis_client,
    )

    app.state.engine = engine
    app.state.redis_client = redis_client
    app.state.session_factory = session_factory
    app.state.recommendation_service = recommendation_service

    yield

    if redis_client:
        try:
            await redis_client.aclose()
        except Exception:
            pass
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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def healthcheck() -> HealthResponse:
        return HealthResponse(app=PRODUCT_NAME)

    app.include_router(session_router, prefix=settings.api_prefix)
    app.include_router(search_router, prefix=settings.api_prefix)
    app.include_router(memory_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    app.include_router(alerts_router, prefix=settings.api_prefix)

    return app


app = create_app()
