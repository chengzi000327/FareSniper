from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.memory import router as memory_router
from backend.api.recommendations import router as recommendations_router
from backend.api.search import router as search_router
from backend.config import settings
from backend.data_sources.ctrip_source import CtripSource
from backend.data_sources.registry import DataSourceRegistry
from backend.db.models import Base
from backend.llm.client import UnifiedLLMClient
from backend.memory.long_term import LongTermMemory
from backend.memory.manager import MemoryManager
from backend.memory.short_term import ShortTermMemory
from backend.memory.summarizer import MemorySummarizer
from backend.schemas.common import HealthResponse
from backend.services.recommendation_service import RecommendationService
from backend.services.search_service import SearchService
from backend.skills._registry import get_default_registry
from backend.agents.intention_agent import IntentionAgent
from backend.agents.orchestration_agent import OrchestrationAgent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── 启动：初始化基础设施 ──────────────────────────────
    engine = create_async_engine(settings.database_url, echo=False) if settings.database_url else None
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None

    # 建表（幂等，启动失败不阻断服务）
    if engine:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            pass

    # ── 记忆系统 ──────────────────────────────────────────
    llm_client = UnifiedLLMClient(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout=settings.request_timeout_seconds,
        default_origin=settings.default_origin,
    )

    session_factory = async_sessionmaker(engine, expire_on_commit=False) if engine else None

    async def _get_memory_manager():
        if redis_client and session_factory:
            async with session_factory() as session:
                stm = ShortTermMemory(redis_client)
                ltm = LongTermMemory(session)
                summarizer = MemorySummarizer(redis_client, llm_client)
                return MemoryManager(stm, ltm, summarizer)
        return None

    # ── 数据源 ────────────────────────────────────────────
    registry = DataSourceRegistry()
    registry.register(CtripSource(enable_mock_fallback=settings.enable_mock_fallback))

    # ── Skill / Agent ─────────────────────────────────────
    skill_registry = get_default_registry()
    intention_agent = IntentionAgent(llm_client=llm_client)
    orchestration_agent = OrchestrationAgent(registry=skill_registry)

    # ── 服务层 ────────────────────────────────────────────
    search_service = SearchService(
        llm_client=llm_client,
        data_source_registry=registry,
        intention_agent=intention_agent,
        orchestration_agent=orchestration_agent,
        session_factory=session_factory,
        redis_client=redis_client,
    )
    recommendation_service = RecommendationService(
        session_factory=session_factory,
        redis_client=redis_client,
    )

    # 挂载到 app.state
    app.state.engine = engine
    app.state.redis_client = redis_client
    app.state.session_factory = session_factory
    app.state.llm_client = llm_client
    app.state.search_service = search_service
    app.state.recommendation_service = recommendation_service
    app.state.skill_registry = skill_registry

    yield

    # ── 关闭：释放资源 ────────────────────────────────────
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
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def healthcheck() -> HealthResponse:
        return HealthResponse(app=settings.app_name)

    app.include_router(search_router, prefix=settings.api_prefix)
    app.include_router(memory_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    return app


app = create_app()
