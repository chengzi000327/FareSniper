from __future__ import annotations

import asyncio
from copy import deepcopy

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
async def test_provider_trace_observes_timeout_instead_of_outer_cancellation(
    monkeypatch,
):
    observed: list[str] = []

    class SlowProvider:
        name = "slow_traced_timeout"

        def supports(self, query) -> bool:
            return True

        async def search(self, query) -> ProviderResult:
            await asyncio.sleep(10)
            raise AssertionError("unreachable")

    async def recording_trace(provider_name, query, operation):
        try:
            return await operation()
        except TimeoutError:
            observed.append("timeout")
            raise
        except asyncio.CancelledError:
            observed.append("cancelled")
            raise

    monkeypatch.setattr(
        "backend.application.services.flight_search_aggregator.trace_provider_call",
        recording_trace,
    )

    result = await FlightSearchAggregator(
        [SlowProvider()], timeout_seconds=0.001
    ).collect(_query())

    assert result["provider_statuses"] == {"slow_traced_timeout": "timeout"}
    assert observed == ["timeout"]


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


def test_public_event_preserves_complete_https_booking_deep_link() -> None:
    events: list[dict] = []
    booking_url = (
        "https://book.example.test/flight"
        "?offer=fixture-token-not-secret&channel=web#checkout"
    )

    with bind_search_event_emitter(SearchEventEmitter("public-link", events.append)):
        emit_search_event(
            "results",
            {
                "deals": [
                    {
                        "booking_url": booking_url,
                        "prices": [{"url": booking_url}],
                    }
                ]
            },
        )

    assert events[0]["payload"]["deals"][0]["booking_url"] == booking_url
    assert events[0]["payload"]["deals"][0]["prices"][0]["url"] == booking_url


def test_public_event_drops_non_https_booking_links() -> None:
    events: list[dict] = []

    with bind_search_event_emitter(SearchEventEmitter("unsafe-link", events.append)):
        emit_search_event(
            "results",
            {
                "deals": [
                    {
                        "booking_url": "http://book.example.test/flight",
                        "prices": [{"url": "javascript:alert(1)"}],
                    }
                ]
            },
        )

    assert events[0]["payload"]["deals"][0]["booking_url"] is None
    assert events[0]["payload"]["deals"][0]["prices"][0]["url"] is None


def test_event_redaction_is_recursive_key_agnostic_and_non_mutating():
    payload = {
        "href": "https://example.test/path?campaign=summer#details",
        "link": "http://example.test/other?token=secret#top",
        "ordinary": "https://example.test/plain?a=1#fragment",
        "relative": "/search?token=secret#frag",
        "scheme_relative": (
            "//book.example.test/path?api_key=secret#frag"
        ),
        "prose": "show fare? maybe later # not a URI",
        "non_uri": "not-a-uri?token=kept#fragment",
        "custom_scheme": "faresniper://book/path?token=kept#fragment",
        "malformed": "https://[",
        "rawPayload": {"secret": "raw"},
        "httpHeaders": {"Authorization": "Bearer secret"},
        "authorizationHeader": "Bearer secret",
        "api-key": "secret-key",
        "nested": [
            "https://example.test/list?tracking=1#row",
            {
                "value": "http://example.test/nested?tracking=2#item",
                "raw-payload": {"secret": "nested-raw"},
            },
        ],
    }
    original = deepcopy(payload)
    events: list[dict] = []

    SearchEventEmitter("redaction", events.append).emit("results", payload)

    clean = events[0]["payload"]
    assert clean["href"] == "https://example.test/path"
    assert clean["link"] == "http://example.test/other"
    assert clean["ordinary"] == "https://example.test/plain"
    assert clean["relative"] == "/search"
    assert clean["scheme_relative"] == "//book.example.test/path"
    assert clean["nested"][0] == "https://example.test/list"
    assert clean["nested"][1]["value"] == "http://example.test/nested"
    assert clean["prose"] == "show fare? maybe later # not a URI"
    assert clean["non_uri"] == "not-a-uri?token=kept#fragment"
    assert clean["custom_scheme"] == (
        "faresniper://book/path?token=kept#fragment"
    )
    assert clean["malformed"] == "https://["
    assert set(clean).isdisjoint(
        {"rawPayload", "httpHeaders", "authorizationHeader", "api-key"}
    )
    assert "raw-payload" not in clean["nested"][1]
    assert payload == original


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
async def test_status_only_results_stay_observable_without_synthetic_deals():
    statuses = {
        "status_queued": ProviderStatus.queued,
        "status_timeout": ProviderStatus.timeout,
        "status_error": ProviderStatus.error,
        "status_disabled": ProviderStatus.disabled,
        "status_empty": ProviderStatus.empty,
    }
    providers = [
        FakeProvider(
            name,
            ProviderResult(
                provider=name,
                status=status,
                error_code=(
                    f"{status.value}_code"
                    if status in {ProviderStatus.timeout, ProviderStatus.error}
                    else None
                ),
            ),
        )
        for name, status in statuses.items()
    ]
    events: list[dict] = []

    with bind_search_event_emitter(SearchEventEmitter("statuses", events.append)):
        result = await FlightSearchAggregator(
            providers, timeout_seconds=0.2
        ).collect(_query())

    assert result["deals"] == []
    assert result["provider_statuses"] == {
        name: status.value for name, status in statuses.items()
    }
    provider_events: dict[str, list[str]] = {name: [] for name in statuses}
    for event in events:
        if event["type"] == "provider_status":
            provider_events[event["payload"]["provider"]].append(
                event["payload"]["status"]
            )
    assert provider_events == {
        name: ["loading", status.value] for name, status in statuses.items()
    }
    result_events = [event for event in events if event["type"] == "results"]
    assert result_events
    assert all(event["payload"]["deals"] == [] for event in result_events)
    assert any(
        "loading" in event["payload"]["provider_statuses"].values()
        for event in result_events
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


@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (ProviderStatus.error, "upstream"),
        (ProviderStatus.timeout, "provider_timeout"),
    ],
)
@pytest.mark.asyncio
async def test_three_returned_failures_open_process_wide_breaker(
    status: ProviderStatus, error_code: str
):
    provider_name = f"returned_{status.value}_breaker"
    provider = FakeProvider(
        provider_name,
        ProviderResult(
            provider=provider_name,
            status=status,
            error_code=error_code,
        ),
    )
    aggregator = FlightSearchAggregator([provider], timeout_seconds=0.2)

    for _ in range(3):
        result = await aggregator.collect(_query())
        assert result["provider_statuses"] == {provider_name: status.value}
        assert result["errors"] == {provider_name: error_code}

    circuit_open = await aggregator.collect(_query())

    assert provider.calls == 3
    assert circuit_open["provider_statuses"] == {provider_name: "error"}
    assert circuit_open["errors"] == {provider_name: "circuit_open"}


@pytest.mark.parametrize(
    "status",
    [
        ProviderStatus.disabled,
        ProviderStatus.empty,
        ProviderStatus.queued,
        ProviderStatus.stale,
        ProviderStatus.success,
    ],
)
@pytest.mark.asyncio
async def test_returned_non_failure_statuses_do_not_open_breaker(
    status: ProviderStatus,
):
    provider_name = f"returned_{status.value}_non_failure"
    provider = FakeProvider(
        provider_name,
        ProviderResult(provider=provider_name, status=status),
    )
    aggregator = FlightSearchAggregator([provider], timeout_seconds=0.2)

    for _ in range(4):
        result = await aggregator.collect(_query())
        assert result["provider_statuses"] == {provider_name: status.value}

    assert provider.calls == 4


@pytest.mark.asyncio
async def test_provider_calls_and_snapshot_stages_use_safe_trace_wrappers(monkeypatch):
    provider = FakeProvider(
        "flyai_traced",
        ProviderResult(
            provider="flyai_traced",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪")],
        ),
    )
    provider_calls: list[tuple[str, object]] = []
    stage_calls: list[tuple[str, dict]] = []

    async def fake_trace_provider_call(provider_name, query, operation):
        provider_calls.append((provider_name, query))
        return await operation()

    def fake_trace_stage(name, inputs, operation):
        stage_calls.append((name, inputs))
        return operation()

    monkeypatch.setattr(
        "backend.application.services.flight_search_aggregator.trace_provider_call",
        fake_trace_provider_call,
    )
    monkeypatch.setattr(
        "backend.application.services.flight_search_aggregator.trace_stage",
        fake_trace_stage,
    )

    result = await FlightSearchAggregator([provider], timeout_seconds=0.2).collect(
        _query()
    )

    assert result["deals"][0]["price"] == 580
    assert [call[0] for call in provider_calls] == ["flyai_traced"]
    assert [name for name, _ in stage_calls] == [
        "normalize_and_deduplicate",
        "rank_results",
        "normalize_and_deduplicate",
        "rank_results",
    ]
    assert all(
        set(inputs)
        <= {
            "origin_code",
            "destination_code",
            "depart_date",
            "provider_count",
            "result_count",
        }
        for _, inputs in stage_calls
    )
