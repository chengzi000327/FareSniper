from __future__ import annotations

import asyncio
from collections.abc import Sequence

from backend.application.contracts.flight_provider import (
    FlightProvider,
    FlightQuery,
    ProviderResult,
    ProviderStatus,
)
from backend.application.services.flight_offer_normalizer import (
    offers_to_deals,
    rank_deals,
)
from backend.application.services.search_events import emit_search_event
from backend.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError


_PROVIDER_BREAKERS: dict[str, CircuitBreaker] = {}
_BREAKER_FAILURE_STATUSES = {ProviderStatus.error, ProviderStatus.timeout}


class _ReturnedProviderFailure(Exception):
    def __init__(self, result: ProviderResult) -> None:
        super().__init__()
        self.result = result


def _breaker_for(provider_name: str) -> CircuitBreaker:
    breaker = _PROVIDER_BREAKERS.get(provider_name)
    if breaker is None:
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        _PROVIDER_BREAKERS[provider_name] = breaker
    return breaker


def _snapshot(
    query: FlightQuery, results: dict[str, ProviderResult]
) -> dict:
    return {
        "deals": rank_deals(offers_to_deals(query, results)),
        "source": "multi_provider",
        "provider_statuses": {
            name: result.status.value for name, result in results.items()
        },
        "errors": {
            name: result.error_code
            for name, result in results.items()
            if result.error_code
        },
    }


class FlightSearchAggregator:
    def __init__(
        self,
        providers: Sequence[FlightProvider],
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._providers = list(providers)
        self._timeout_seconds = timeout_seconds

    async def _collect_provider(
        self, provider: FlightProvider, query: FlightQuery
    ) -> tuple[str, ProviderResult]:
        async def search_with_timeout() -> ProviderResult:
            result = await asyncio.wait_for(
                provider.search(query), timeout=self._timeout_seconds
            )
            if result.status in _BREAKER_FAILURE_STATUSES:
                raise _ReturnedProviderFailure(result)
            return result

        try:
            result = await _breaker_for(provider.name).call(search_with_timeout)
        except _ReturnedProviderFailure as exc:
            result = exc.result
        except CircuitOpenError:
            result = ProviderResult(
                provider=provider.name,
                status=ProviderStatus.error,
                error_code="circuit_open",
                message="来源暂时熔断",
            )
        except TimeoutError:
            result = ProviderResult(
                provider=provider.name,
                status=ProviderStatus.timeout,
            )
        except Exception:
            result = ProviderResult(
                provider=provider.name,
                status=ProviderStatus.error,
                error_code="provider_error",
            )
        return provider.name, result

    async def collect(self, query: FlightQuery) -> dict:
        providers = [
            provider for provider in self._providers if provider.supports(query)
        ]
        results = {
            provider.name: ProviderResult(
                provider=provider.name, status=ProviderStatus.loading
            )
            for provider in providers
        }
        emit_search_event(
            "started",
            {
                "providers": [provider.name for provider in providers],
                "origin": query.origin_code,
                "destination": query.destination_code,
                "depart_date": query.depart_date,
            },
        )
        for provider in providers:
            emit_search_event(
                "provider_status",
                {"provider": provider.name, "status": ProviderStatus.loading.value},
            )

        tasks = [
            asyncio.create_task(self._collect_provider(provider, query))
            for provider in providers
        ]
        try:
            for completed in asyncio.as_completed(tasks):
                provider_name, result = await completed
                results[provider_name] = result
                emit_search_event(
                    "provider_status",
                    {"provider": provider_name, "status": result.status.value},
                )
                emit_search_event("results", _snapshot(query, results))
        finally:
            unfinished = [task for task in tasks if not task.done()]
            for task in unfinished:
                task.cancel()
            if unfinished:
                await asyncio.gather(*unfinished, return_exceptions=True)

        return _snapshot(query, results)
