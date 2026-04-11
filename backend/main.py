from __future__ import annotations

from fastapi import FastAPI

from backend.api.memory import router as memory_router
from backend.api.recommendations import router as recommendations_router
from backend.api.search import router as search_router
from backend.config import settings
from backend.data_sources.ctrip_source import CtripSource
from backend.data_sources.registry import DataSourceRegistry
from backend.llm.client import LLMClient
from backend.schemas.common import HealthResponse
from backend.services.memory_service import MemoryService
from backend.services.recommendation_service import RecommendationService
from backend.services.search_service import SearchService


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    memory_service = MemoryService(settings.memory_file)
    llm_client = LLMClient(settings)

    registry = DataSourceRegistry()
    registry.register(CtripSource(enable_mock_fallback=settings.enable_mock_fallback))

    app.state.memory_service = memory_service
    app.state.search_service = SearchService(
        llm_client=llm_client,
        memory_service=memory_service,
        data_source_registry=registry,
    )
    app.state.recommendation_service = RecommendationService(memory_service=memory_service)

    @app.on_event("startup")
    async def _startup() -> None:
        await memory_service.ensure_initialized()

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def healthcheck() -> HealthResponse:
        return HealthResponse(app=settings.app_name)

    app.include_router(search_router, prefix=settings.api_prefix)
    app.include_router(memory_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    return app


app = create_app()
