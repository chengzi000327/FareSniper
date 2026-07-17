from __future__ import annotations

import asyncio

import pytest

from backend.application.contracts.flight_provider import (
    FlightOffer,
    ProviderResult,
    ProviderStatus,
)
from backend.application.services.flight_query import build_flight_query
from backend.application.services.flight_search_aggregator import FlightSearchAggregator
from backend.application.services.search_events import (
    SearchEventEmitter,
    bind_search_event_emitter,
    emit_search_event,
)


def _query():
    return build_flight_query("北京", "上海", "2099-08-01")


def _offer(*, provider: str, seller: str, price: int = 580) -> FlightOffer:
    return FlightOffer(
        data_provider=provider,
        seller_name=seller,
        flight_no="CA1835",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        depart_time="08:00",
        total_price=price,
    )


class FakeProvider:
    def __init__(
        self,
        name: str,
        result: ProviderResult | None = None,
        *,
        error: Exception | None = None,
        supported: bool = True,
    ) -> None:
        self.name = name
        self.result = result
        self.error = error
        self.supported = supported
        self.calls = 0

    def supports(self, query) -> bool:
        return self.supported

    async def search(self, query) -> ProviderResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@pytest.mark.asyncio
async def test_partial_success_survives_other_error():
    flyai = FakeProvider(
        "flyai_partial",
        ProviderResult(
            provider="flyai_partial",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪")],
        ),
    )
    ctrip = FakeProvider(
        "ctrip_partial",
        ProviderResult(
            provider="ctrip_partial",
            status=ProviderStatus.error,
            error_code="upstream",
        ),
    )

    result = await FlightSearchAggregator(
        [flyai, ctrip], timeout_seconds=0.2
    ).collect(_query())

    assert result["deals"][0]["price"] == 580
    assert result["provider_statuses"]["ctrip_partial"] == "error"
    assert result["errors"] == {"ctrip_partial": "upstream"}


@pytest.mark.asyncio
async def test_timeout_does_not_discard_fast_result_and_cancels_slow_search():
    cancelled = asyncio.Event()

    class SlowProvider:
        name = "slow_timeout"

        def supports(self, query) -> bool:
            return True

        async def search(self, query) -> ProviderResult:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            raise AssertionError("unreachable")

    fast = FakeProvider(
        "fast_timeout",
        ProviderResult(
            provider="fast_timeout",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪")],
        ),
    )

    result = await FlightSearchAggregator(
        [SlowProvider(), fast], timeout_seconds=0.01
    ).collect(_query())

    assert result["provider_statuses"] == {
        "slow_timeout": "timeout",
        "fast_timeout": "success",
    }
    assert result["deals"][0]["price"] == 580
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_applicable_providers_start_concurrently():
    both_started = asyncio.Event()
    started = 0

    class RendezvousProvider:
        def __init__(self, name: str) -> None:
            self.name = name

        def supports(self, query) -> bool:
            return True

        async def search(self, query) -> ProviderResult:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.1)
            return ProviderResult(provider=self.name, status=ProviderStatus.empty)

    result = await FlightSearchAggregator(
        [RendezvousProvider("overlap_a"), RendezvousProvider("overlap_b")],
        timeout_seconds=0.2,
    ).collect(_query())

    assert result["provider_statuses"] == {
        "overlap_a": "empty",
        "overlap_b": "empty",
    }


@pytest.mark.asyncio
async def test_unsupported_provider_is_not_scheduled():
    provider = FakeProvider("unsupported", supported=False)

    result = await FlightSearchAggregator([provider], timeout_seconds=0.2).collect(
        _query()
    )

    assert result["provider_statuses"] == {}
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_collect_cancellation_cancels_and_awaits_provider_tasks():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class HangingProvider:
        name = "hanging_cancel"

        def supports(self, query) -> bool:
            return True

        async def search(self, query) -> ProviderResult:
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise
            raise AssertionError("unreachable")

    task = asyncio.create_task(
        FlightSearchAggregator([HangingProvider()], timeout_seconds=5).collect(
            _query()
        )
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_events_are_request_scoped_sanitized_and_reset():
    left: list[dict] = []
    right: list[dict] = []
    rendezvous = asyncio.Event()
    bound = 0

    async def run(search_id: str, sink: list[dict]) -> None:
        nonlocal bound
        with bind_search_event_emitter(SearchEventEmitter(search_id, sink.append)):
            bound += 1
            if bound == 2:
                rendezvous.set()
            await rendezvous.wait()
            emit_search_event(
                "results",
                {
                    "api_key": "must-not-leak",
                    "X-API-Key": "header-key-must-not-leak",
                    "headers": {"Authorization": "bearer-must-not-leak"},
                    "raw_payload": {"secret": "raw-must-not-leak"},
                    "url": "https://book.example.test/f?utm_source=secret&token=x",
                },
            )

    await asyncio.gather(run("left", left), run("right", right))
    emit_search_event("outside", {"value": "ignored"})

    assert [event["search_id"] for event in left] == ["left"]
    assert [event["search_id"] for event in right] == ["right"]
    assert left[0]["sequence"] == right[0]["sequence"] == 1
    assert "must-not-leak" not in str(left + right)
    assert "?" not in left[0]["payload"]["url"]


@pytest.mark.asyncio
async def test_events_report_loading_then_completion_without_exception_details():
    events: list[dict] = []
    provider = FakeProvider(
        "safe_error",
        error=RuntimeError("secret upstream exception detail"),
    )

    with bind_search_event_emitter(SearchEventEmitter("search-1", events.append)):
        result = await FlightSearchAggregator(
            [provider], timeout_seconds=0.2
        ).collect(_query())

    statuses = [
        event["payload"]["status"]
        for event in events
        if event["type"] == "provider_status"
    ]
    assert statuses == ["loading", "error"]
    assert result["errors"] == {"safe_error": "provider_error"}
    assert "secret upstream" not in str(events)
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )


@pytest.mark.asyncio
async def test_three_provider_timeouts_open_process_wide_breaker():
    class TimeoutProvider:
        name = "timeout_breaker_threshold"

        def __init__(self) -> None:
            self.calls = 0

        def supports(self, query) -> bool:
            return True

        async def search(self, query) -> ProviderResult:
            self.calls += 1
            await asyncio.sleep(10)
            raise AssertionError("unreachable")

    provider = TimeoutProvider()
    aggregator = FlightSearchAggregator([provider], timeout_seconds=0.001)

    for _ in range(3):
        result = await aggregator.collect(_query())
        assert result["provider_statuses"][provider.name] == "timeout"

    circuit_open = await aggregator.collect(_query())

    assert provider.calls == 3
    assert circuit_open["errors"] == {provider.name: "circuit_open"}
