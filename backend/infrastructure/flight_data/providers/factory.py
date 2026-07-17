from __future__ import annotations

from functools import lru_cache

from backend.application.contracts.flight_provider import FlightProvider
from backend.config import settings
from backend.infrastructure.flight_data.providers.ctrip_snapshot import (
    CtripSnapshotProvider,
)
from backend.infrastructure.flight_data.providers.flyai import FlyAIProvider
from backend.infrastructure.flight_data.providers.serpapi import SerpApiProvider


@lru_cache(maxsize=1)
def _provider_instances() -> tuple[FlightProvider, ...]:
    return (
        FlyAIProvider(
            api_key=settings.flyai_api_key,
            cli_path=settings.flyai_cli_path,
            timeout_seconds=settings.flight_provider_timeout_seconds,
        ),
        CtripSnapshotProvider(),
        SerpApiProvider(api_key=settings.serpapi_api_key),
    )


def build_flight_providers() -> list[FlightProvider]:
    return list(_provider_instances())
