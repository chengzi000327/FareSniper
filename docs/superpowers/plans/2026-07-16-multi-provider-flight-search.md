# FareSniper Multi-Provider Flight Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace production mock fare search with progressive FlyAI, hourly Ctrip snapshot, and SerpAPI Google Flights results while preserving the existing FareSniper card UI and emitting provider-level LangSmith traces.

**Architecture:** A typed `FlightProvider` boundary normalizes FlyAI CLI, SerpAPI HTTP, and Ctrip snapshot data into `FlightOffer` objects. `FlightSearchAggregator` runs applicable providers concurrently, emits NDJSON events through a request-scoped emitter, and returns the same final response through the existing JSON API. Ctrip browser work remains in the external Railway worker and writes 75-minute snapshots once per hour.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, asyncio, httpx, SQLAlchemy async, Alembic, PostgreSQL, APScheduler, LangGraph, LangSmith, Node.js 22, `@fly-ai/flyai-cli@1.0.16`, Next.js 15, React 19, TypeScript, Vitest, pytest.

## Global Constraints

- Scope is flights only. Do not add hotel or RollingGo code.
- Keep the existing `DiscoveryCardContent` layout; add nullable fare fields and source-state rendering.
- Mainland domestic routes use FlyAI live plus Ctrip snapshots. International/Hong Kong/Macao/Taiwan routes use FlyAI, SerpAPI, and matching Ctrip snapshots.
- Real-time Provider timeout is exactly 10 seconds. One failure never discards another Provider's success.
- Ctrip collection runs in the external worker once per hour; freshness is exactly 75 minutes.
- FlyAI receives a future date and normalized Chinese full city names.
- Pin `@fly-ai/flyai-cli` to `1.0.16`. Never run `npx` in a request.
- `FLYAI_API_KEY` and `SERPAPI_API_KEY` are Railway variables; committed examples contain empty values.
- FlyAI offers without price remain `view_live_price` only when an HTTPS `jumpUrl` exists and never win lowest-price ranking.
- Unknown tax, baggage fee, or baggage allowance stays `null`, never zero or “free”.
- SerpAPI labels use booking seller, then `ticket_also_sold_by`, then operating airline.
- Card source rows use stable order: 携程 first, 飞猪 second, then international sellers.
- Production search never emits mock fares. VariFlight stays available for schedule/status enrichment only.
- Traces never contain keys, cookies, Authorization headers, raw environments, full payloads, or tracking query strings.
- Preserve `POST /api/search` and add `POST /api/search/stream` with NDJSON.

---

## File Map

| File | Responsibility |
| --- | --- |
| `backend/application/contracts/flight_provider.py` | Query, offer, result, status, and Provider protocol |
| `backend/application/services/flight_query.py` | Future-date validation and city/route normalization |
| `backend/application/services/search_events.py` | Request-scoped event emitter |
| `backend/application/services/flight_offer_normalizer.py` | Deduplication, seller rows, and card conversion |
| `backend/application/services/flight_search_aggregator.py` | Concurrent Provider orchestration |
| `backend/infrastructure/flight_data/providers/flyai.py` | Safe FlyAI CLI adapter |
| `backend/infrastructure/flight_data/providers/serpapi.py` | Google Flights and booking-option adapter |
| `backend/infrastructure/flight_data/providers/ctrip_snapshot.py` | Online Ctrip snapshot adapter |
| `backend/infrastructure/db/flight_demand_repo.py` | Search-demand queue and worker lease |
| `backend/workers/ctrip_refresh.py` | Hourly Ctrip collection batch |
| `backend/api/search.py` | JSON and NDJSON search endpoints |
| `frontend/lib/api.ts` | Authenticated NDJSON reader and DTOs |
| `frontend/components/discovery-card-content.tsx` | Nullable fares and Provider states |
| `frontend/components/chat-page.tsx` | Progressive updates in the existing card |
| `backend/infrastructure/observability/provider_tracing.py` | Safe LangSmith spans |

---

### Task 1: Provider Contracts, City Resolution, and Settings

**Files:**
- Create: `backend/application/contracts/flight_provider.py`
- Create: `backend/application/services/flight_query.py`
- Modify: `backend/utils/airport_codes.py`
- Modify: `backend/config.py`
- Modify: `backend/schemas/common.py`
- Test: `backend/tests/contracts/test_flight_provider_contracts.py`
- Test: `backend/tests/services/test_flight_query.py`
- Modify test: `backend/tests/test_settings_contract.py`

**Interfaces:**
- Produces `build_flight_query(origin: str, destination: str, depart_date: str, *, today: date | None = None) -> FlightQuery`.
- Produces `FlightProvider.search(query: FlightQuery) -> ProviderResult`.
- Makes fare and fee fields nullable end to end.

- [ ] **Step 1: Write failing tests**

~~~python
# backend/tests/contracts/test_flight_provider_contracts.py
from backend.application.contracts.flight_provider import (
    FlightOffer, PriceStatus, ProviderResult, ProviderStatus,
)

def test_offer_keeps_unknown_fees_and_live_link():
    offer = FlightOffer(
        data_provider="flyai", seller_name="飞猪", flight_no="CA1835",
        origin_city="北京", origin_code="BJS",
        destination_city="上海", destination_code="SHA",
        depart_date="2099-08-01", total_price=None, tax=None,
        baggage_fee=None, has_baggage=None,
        price_status=PriceStatus.view_live_price,
        booking_url="https://example.test/flight",
    )
    assert offer.total_price is None
    assert offer.price_status is PriceStatus.view_live_price

def test_disabled_and_empty_are_distinct():
    assert ProviderResult(
        provider="flyai", status=ProviderStatus.disabled
    ).status != ProviderResult(
        provider="flyai", status=ProviderStatus.empty
    ).status
~~~

~~~python
# backend/tests/services/test_flight_query.py
from datetime import date
import pytest
from backend.application.services.flight_query import (
    FlightQueryValidationError, build_flight_query,
)

def test_code_normalizes_to_chinese_city():
    query = build_flight_query("BJS", "SHA", "2099-08-01", today=date(2026, 7, 16))
    assert (query.origin_city, query.destination_city) == ("北京", "上海")
    assert query.is_mainland_domestic is True

def test_hong_kong_is_not_mainland_domestic():
    query = build_flight_query("上海", "香港", "2099-08-01", today=date(2026, 7, 16))
    assert query.destination_code == "HKG"
    assert query.is_mainland_domestic is False

def test_serpapi_ids_are_separate_from_ctrip_city_code():
    query = build_flight_query(
        "上海", "新加坡", "2099-08-01", today=date(2026, 7, 16)
    )
    assert query.origin_code == "SHA"
    assert query.origin_airport_ids == ["PVG", "SHA"]
    assert query.destination_airport_ids == ["SIN"]

@pytest.mark.parametrize("value", ["2026-07-15", "2026-07-16", "not-a-date"])
def test_rejects_non_future_or_invalid_date(value):
    with pytest.raises(FlightQueryValidationError):
        build_flight_query("北京", "上海", value, today=date(2026, 7, 16))

def test_unknown_city_is_not_guessed():
    with pytest.raises(FlightQueryValidationError, match="无法识别"):
        build_flight_query("不存在的城市", "上海", "2099-08-01", today=date(2026, 7, 16))
~~~

- [ ] **Step 2: Verify failure**

Run:

~~~bash
pytest backend/tests/contracts/test_flight_provider_contracts.py backend/tests/services/test_flight_query.py -v
~~~

Expected: collection fails because both implementation modules are absent.

- [ ] **Step 3: Add Provider contracts**

~~~python
# backend/application/contracts/flight_provider.py
from __future__ import annotations
from enum import Enum
from typing import Protocol
from pydantic import BaseModel, Field

class ProviderStatus(str, Enum):
    loading = "loading"
    queued = "queued"
    success = "success"
    empty = "empty"
    stale = "stale"
    timeout = "timeout"
    disabled = "disabled"
    error = "error"

class PriceStatus(str, Enum):
    priced = "priced"
    view_live_price = "view_live_price"
    stale = "stale"

class FlightQuery(BaseModel):
    origin_city: str
    origin_code: str
    origin_airport_ids: list[str]
    destination_city: str
    destination_code: str
    destination_airport_ids: list[str]
    depart_date: str
    currency: str = "CNY"
    is_mainland_domestic: bool

class FlightOffer(BaseModel):
    data_provider: str
    seller_name: str
    flight_no: str
    airline: str = ""
    origin_city: str
    origin_code: str
    destination_city: str
    destination_code: str
    depart_date: str
    depart_time: str = ""
    arrive_time: str = ""
    duration_minutes: int | None = None
    stops: int = 0
    cabin: str | None = None
    currency: str = "CNY"
    base_price: int | None = None
    tax: int | None = None
    baggage_fee: int | None = None
    total_price: int | None = None
    has_baggage: bool | None = None
    price_status: PriceStatus = PriceStatus.priced
    booking_url: str | None = None
    fetched_at: str | None = None
    expires_at: str | None = None
    is_realtime: bool = True
    raw_reference: str | None = None

class ProviderResult(BaseModel):
    provider: str
    status: ProviderStatus
    offers: list[FlightOffer] = Field(default_factory=list)
    error_code: str | None = None
    message: str = ""
    latency_ms: int = 0
    cache_age_seconds: int | None = None

class FlightProvider(Protocol):
    name: str
    def supports(self, query: FlightQuery) -> bool: ...
    async def search(self, query: FlightQuery) -> ProviderResult: ...
~~~

- [ ] **Step 4: Replace airport maps and implement query validation**

Use an immutable `AirportRef(city, code, airport_ids, mainland_china)` catalog in `airport_codes.py`. `code` is the current internal/Ctrip city code; `airport_ids` are the actual IATA IDs sent to SerpAPI. Required multi-airport mappings include Beijing `("PEK", "PKX")`, Shanghai `("PVG", "SHA")`, Tokyo `("HND", "NRT")`, Seoul `("ICN", "GMP")`, London `("LHR", "LGW")`, Paris `("CDG", "ORY")`, and New York `("JFK", "EWR", "LGA")`. Preserve all current cities and add:

~~~python
("香港", "HKG", False), ("澳门", "MFM", False), ("台北", "TPE", False),
("东京", "TYO", False), ("大阪", "OSA", False), ("首尔", "SEL", False),
("新加坡", "SIN", False), ("曼谷", "BKK", False), ("吉隆坡", "KUL", False),
("伦敦", "LON", False), ("巴黎", "PAR", False), ("纽约", "NYC", False),
("洛杉矶", "LAX", False), ("悉尼", "SYD", False),
("乌鲁木齐", "URC", True), ("哈尔滨", "HRB", True),
("青岛", "TAO", True), ("大连", "DLC", True),
~~~

Expose `resolve_airport(value: str) -> AirportRef | None` while preserving `city_to_code` and `code_to_city`.

~~~python
# backend/application/services/flight_query.py
from datetime import date, datetime
from zoneinfo import ZoneInfo
from backend.application.contracts.flight_provider import FlightQuery
from backend.utils.airport_codes import resolve_airport

class FlightQueryValidationError(ValueError):
    pass

def build_flight_query(origin, destination, depart_date, *, today=None):
    origin_ref = resolve_airport(origin)
    destination_ref = resolve_airport(destination)
    if origin_ref is None:
        raise FlightQueryValidationError(f"无法识别出发城市：{origin}")
    if destination_ref is None:
        raise FlightQueryValidationError(f"无法识别到达城市：{destination}")
    try:
        parsed = date.fromisoformat(depart_date)
    except ValueError as exc:
        raise FlightQueryValidationError("出发日期必须使用 YYYY-MM-DD") from exc
    current = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if parsed <= current:
        raise FlightQueryValidationError("出发日期必须是未来日期")
    return FlightQuery(
        origin_city=origin_ref.city, origin_code=origin_ref.code,
        origin_airport_ids=list(origin_ref.airport_ids),
        destination_city=destination_ref.city, destination_code=destination_ref.code,
        destination_airport_ids=list(destination_ref.airport_ids),
        depart_date=parsed.isoformat(),
        is_mainland_domestic=origin_ref.mainland_china and destination_ref.mainland_china,
    )
~~~

- [ ] **Step 5: Add settings and nullable DTO fields**

Add to `Settings`:

~~~python
flyai_api_key: str = Field(default="")
flyai_cli_path: str = Field(default="flyai")
serpapi_api_key: str = Field(default="")
flight_provider_timeout_seconds: float = Field(default=10.0)
ctrip_snapshot_ttl_minutes: int = Field(default=75)
ctrip_refresh_batch_size: int = Field(default=20)
ctrip_request_delay_min_seconds: float = Field(default=2.0)
ctrip_request_delay_max_seconds: float = Field(default=5.0)
run_scheduler_in_api: bool = Field(default=False)
enable_mock_fallback: bool = Field(default=False)
~~~

Update `PriceItemDto` with nullable `price` plus `status`, `url`, and `data_provider`. Update `DealCardDto` so `price`, `tax`, `baggage_fee`, and `has_baggage` are nullable, and add nullable `total_price` plus `currency="CNY"`.

- [ ] **Step 6: Verify and commit**

Run:

~~~bash
pytest backend/tests/contracts/test_flight_provider_contracts.py backend/tests/services/test_flight_query.py backend/tests/test_settings_contract.py backend/tests/test_schemas.py -v
~~~

Expected: all selected tests pass.

~~~bash
git add backend/application/contracts/flight_provider.py backend/application/services/flight_query.py backend/utils/airport_codes.py backend/config.py backend/schemas/common.py backend/tests/contracts/test_flight_provider_contracts.py backend/tests/services/test_flight_query.py backend/tests/test_settings_contract.py
git commit -m "feat(flights): add provider contracts and query validation"
~~~

---

### Task 2: FlyAI CLI Provider

**Files:**
- Create: `backend/infrastructure/flight_data/providers/__init__.py`
- Create: `backend/infrastructure/flight_data/providers/flyai.py`
- Create fixture: `backend/tests/fixtures/providers/flyai_search_success.json`
- Create test: `backend/tests/infra/test_flyai_provider.py`

**Interfaces:**
- Consumes `FlightQuery` and produces `FlyAIProvider.search(query) -> ProviderResult`.
- Provider name is `flyai` and visible seller is `飞猪`.

- [ ] **Step 1: Add official-shape fixture and failing tests**

The fixture contains `data.itemList[0].adultPrice`, `journeys[].segments[]`, and an HTTPS `jumpUrl` matching the official reference.

~~~python
def test_parse_maps_price_flight_and_jump_url():
    payload = json.loads(FIXTURE.read_text())
    offers = parse_flyai_payload(
        payload, build_flight_query("北京", "上海", "2099-08-01")
    )
    assert offers[0].seller_name == "飞猪"
    assert offers[0].total_price == 400
    assert offers[0].flight_no == "CA1883"
    assert offers[0].booking_url.startswith("https://")

def test_missing_price_becomes_view_live_price():
    payload = json.loads(FIXTURE.read_text())
    del payload["data"]["itemList"][0]["adultPrice"]
    offer = parse_flyai_payload(
        payload, build_flight_query("北京", "上海", "2099-08-01")
    )[0]
    assert offer.total_price is None
    assert offer.price_status is PriceStatus.view_live_price

@pytest.mark.asyncio
async def test_missing_key_disables_provider():
    result = await FlyAIProvider(api_key="").search(
        build_flight_query("北京", "上海", "2099-08-01")
    )
    assert result.status is ProviderStatus.disabled
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/infra/test_flyai_provider.py -v
~~~

Expected: import failure for `FlyAIProvider`.

- [ ] **Step 3: Implement parser and subprocess**

`parse_flyai_payload` must parse `adultPrice` with `Decimal`, flatten journey segments, join flight numbers with `/`, compute stops, and reject non-HTTPS URLs. Implement:

~~~python
class FlyAIProvider:
    name = "flyai"

    def __init__(self, *, api_key, cli_path="flyai", timeout_seconds=10.0):
        self._api_key = api_key
        self._cli_path = cli_path
        self._timeout_seconds = timeout_seconds

    def supports(self, query):
        return True

    async def search(self, query):
        if not self._api_key:
            return ProviderResult(provider=self.name, status=ProviderStatus.disabled)
        env = os.environ.copy()
        env["FLYAI_API_KEY"] = self._api_key
        process = await asyncio.create_subprocess_exec(
            self._cli_path, "search-flight",
            "--origin", query.origin_city,
            "--destination", query.destination_city,
            "--dep-date", query.depart_date,
            "--sort-type", "3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return ProviderResult(provider=self.name, status=ProviderStatus.timeout)
        if process.returncode != 0:
            text = stderr.decode("utf-8", errors="replace").lower()
            auth = any(token in text for token in ("401", "unauthorized", "api key"))
            return ProviderResult(
                provider=self.name, status=ProviderStatus.error,
                error_code="authentication" if auth else "cli_failed",
            )
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ProviderResult(
                provider=self.name, status=ProviderStatus.error,
                error_code="invalid_json",
            )
        offers = parse_flyai_payload(payload, query)
        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.success if offers else ProviderStatus.empty,
            offers=offers,
        )
~~~

The parser sets unknown tax/baggage fields to `None` and sets `view_live_price` only when price is missing and `jumpUrl` is valid HTTPS. Skip an item when both numeric price and valid `jumpUrl` are absent. If CLI exit is zero but payload `status` is nonzero, return `ProviderStatus.error` with `error_code="upstream_response"`.

- [ ] **Step 4: Test safe arguments, timeout, and auth classification**

Monkeypatch `asyncio.create_subprocess_exec` and assert Chinese city names are separate arguments, the key is in inherited env only, and no shell is used. Add fake timeout, nonzero payload status, and nonzero-return tests. Extract one CLI execution into `_run_once`; retry exactly once only when stderr identifies timeout, connection reset, or temporary network failure. Never retry authentication or invalid JSON.

~~~bash
pytest backend/tests/infra/test_flyai_provider.py -v
~~~

Expected: all tests pass without a real CLI.

- [ ] **Step 5: Commit**

~~~bash
git add backend/infrastructure/flight_data/providers backend/tests/fixtures/providers/flyai_search_success.json backend/tests/infra/test_flyai_provider.py
git commit -m "feat(flights): add FlyAI CLI provider"
~~~

---

### Task 3: SerpAPI International Provider

**Files:**
- Create: `backend/infrastructure/flight_data/providers/serpapi.py`
- Create fixtures: `backend/tests/fixtures/providers/serpapi_search.json`, `backend/tests/fixtures/providers/serpapi_booking_options.json`
- Create test: `backend/tests/infra/test_serpapi_provider.py`

**Interfaces:**
- Uses `engine=google_flights`, `type=2`, `currency=CNY`, `sort_by=2`.
- Resolves booking options for at most the three cheapest token-bearing itineraries.

- [ ] **Step 1: Add fixtures and failing tests**

The search fixture contains `search_metadata.google_flights_url`, one `best_flights` item, `booking_token`, price, flight number, airline, and `ticket_also_sold_by`. The booking fixture contains `booking_options[0].together.book_with`, price, and an HTTPS GET-only `booking_request.url`.

~~~python
@pytest.mark.asyncio
async def test_uses_actual_booking_seller():
    async def handler(request):
        payload = BOOKING if request.url.params.get("booking_token") else SEARCH
        return httpx.Response(200, json=payload)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SerpApiProvider(api_key="secret", client=client)
    result = await provider.search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()
    assert result.status is ProviderStatus.success
    assert result.offers[0].seller_name == "Trip.com"
    assert result.offers[0].data_provider == "serpapi_google_flights"
    assert result.offers[0].total_price == 2860

def test_mainland_route_is_not_supported():
    assert SerpApiProvider(api_key="x").supports(
        build_flight_query("北京", "上海", "2099-08-01")
    ) is False
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/infra/test_serpapi_provider.py -v
~~~

Expected: import failure for `SerpApiProvider`.

- [ ] **Step 3: Implement search and seller fallback**

`SerpApiProvider.search` sends:

~~~python
params = {
    "engine": "google_flights",
    "departure_id": ",".join(query.origin_airport_ids),
    "arrival_id": ",".join(query.destination_airport_ids),
    "outbound_date": query.depart_date,
    "type": "2",
    "currency": query.currency,
    "hl": "zh-cn",
    "gl": "cn",
    "sort_by": "2",
    "adults": "1",
    "api_key": self._api_key,
}
~~~

Merge `best_flights` and `other_flights`. Resolve at most three booking tokens concurrently. Seller precedence is:

~~~python
seller = (
    booking_option.get("book_with")
    or first_leg.get("ticket_also_sold_by", [None])[0]
    or first_leg.get("airline")
    or "Google Flights"
)
~~~

Use direct `booking_request.url` only when it is HTTPS and `post_data` is absent. Otherwise use `search_metadata.google_flights_url`. Classify 401/403 as `authentication`, 429 as `rate_limited`, other HTTP failures as `upstream_http`, and network failures as `network`. `_get` retries exactly once with jitter for 429, temporary 5xx, timeout, or connection reset; it never retries 401/403 or response validation errors.

- [ ] **Step 4: Add request, fallback, and error tests**

Assert `departure_id=PVG,SHA`, `arrival_id=SIN`, `type=2`, and `currency=CNY`. Add a POST-only booking fixture and verify Google Flights URL fallback. Add a 401 no-retry test and a 429-then-200 test asserting exactly two calls.

~~~bash
pytest backend/tests/infra/test_serpapi_provider.py -v
~~~

Expected: all tests pass with `httpx.MockTransport` and no live requests.

- [ ] **Step 5: Commit**

~~~bash
git add backend/infrastructure/flight_data/providers/serpapi.py backend/tests/fixtures/providers/serpapi_search.json backend/tests/fixtures/providers/serpapi_booking_options.json backend/tests/infra/test_serpapi_provider.py
git commit -m "feat(flights): add SerpAPI international provider"
~~~

---

### Task 4: Ctrip Demand Queue and Provider-Scoped Snapshots

**Files:**
- Create migration: `backend/db/migrations/versions/20260716_provider_snapshots.py`
- Create: `backend/infrastructure/db/flight_demand_repo.py`
- Modify: `backend/infrastructure/db/flight_snapshot_repo.py`
- Create: `backend/infrastructure/flight_data/providers/ctrip_snapshot.py`
- Create tests: `backend/tests/infra/test_flight_demand_repo.py`, `backend/tests/infra/test_ctrip_snapshot_provider.py`
- Modify test: `backend/tests/infra/test_flight_snapshot_repo.py`

**Interfaces:**
- Produces `enqueue_demand(...) -> None` and `claim_due_demands(limit: int) -> list[FlightSearchDemand]`.
- Produces `upsert_provider_flights(provider: str, flights: list[dict], ttl_minutes: int) -> None`.
- Produces `read_provider_deals(...) -> tuple[list[dict], int | None, bool]`.
- Produces `CtripSnapshotProvider.search(query) -> ProviderResult`.

- [ ] **Step 1: Write failing repository tests**

~~~python
# backend/tests/infra/test_flight_demand_repo.py
@pytest.mark.asyncio
async def test_enqueue_is_idempotent_and_raises_priority(seeded_pg):
    await enqueue_demand(
        origin_code="BJS", destination_code="SHA", depart_date="2099-08-01",
        priority=10, source="recent_search",
    )
    await enqueue_demand(
        origin_code="BJS", destination_code="SHA", depart_date="2099-08-01",
        priority=100, source="price_alert",
    )
    rows = await claim_due_demands(limit=10)
    assert len(rows) == 1
    assert rows[0].priority == 100
    assert rows[0].source == "price_alert"
~~~

~~~python
# append to backend/tests/infra/test_flight_snapshot_repo.py
@pytest.mark.asyncio
async def test_provider_upsert_preserves_other_provider_rows(seeded_pg):
    base = {
        "flight_no": "MU5106", "airline": "东方航空",
        "origin_code": "BJS", "destination_code": "SHA",
        "depart_date": "2099-08-01", "dep_time": "08:00",
        "arr_time": "10:00", "duration": "120分钟", "stops": 0,
    }
    await upsert_provider_flights(
        "ctrip_snapshot",
        [{**base, "prices": [{"platform": "携程", "price": 580, "url": "https://ctrip.test"}]}],
        ttl_minutes=75,
    )
    await upsert_provider_flights(
        "legacy",
        [{**base, "prices": [{"platform": "legacy", "price": 600, "url": "https://legacy.test"}]}],
        ttl_minutes=60,
    )
    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot", origin_code="BJS",
        destination_code="SHA", depart_date="2099-08-01",
    )
    assert len(rows) == 1
    assert rows[0]["prices"][0]["platform"] == "携程"
    assert age is not None
    assert stale is False
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py -v
~~~

Expected: imports fail for the new demand and provider-scoped functions.

- [ ] **Step 3: Add Alembic revision**

Create revision `20260716_provider_snapshots` with down revision `20260601_flight_snapshots`. Upgrade:

~~~python
def upgrade() -> None:
    op.add_column(
        "platform_price_snapshots",
        sa.Column("data_provider", sa.String(), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("currency", sa.String(), nullable=False, server_default="CNY"),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("price_status", sa.String(), nullable=False, server_default="priced"),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_platform_price_provider_flight",
        "platform_price_snapshots",
        ["data_provider", "flight_snapshot_id"],
    )
    op.create_table(
        "flight_search_demands",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("origin_code", sa.String(), nullable=False),
        sa.Column("destination_code", sa.String(), nullable=False),
        sa.Column("depart_date", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint(
            "origin_code", "destination_code", "depart_date",
            name="uq_flight_search_demand_route_date",
        ),
    )
    op.create_index(
        "ix_flight_search_demands_due",
        "flight_search_demands",
        ["active", "next_run_at", "priority"],
    )
~~~

Downgrade drops the demand table, Provider index, and added columns in reverse order.

- [ ] **Step 4: Implement demand upsert and claim**

Define `FlightSearchDemandRow` on the canonical `Base` and immutable dataclass `FlightSearchDemand`. Implement:

~~~python
async def enqueue_demand(
    *, origin_code, destination_code, depart_date, priority, source,
):
    now = datetime.now(timezone.utc)
    demand_id = hashlib.sha1(
        f"{origin_code}|{destination_code}|{depart_date}".encode()
    ).hexdigest()[:24]
    values = {
        "id": demand_id,
        "origin_code": origin_code,
        "destination_code": destination_code,
        "depart_date": depart_date,
        "priority": priority,
        "source": source,
        "last_requested_at": now,
        "next_run_at": now,
        "expires_at": now + timedelta(days=7),
        "active": True,
    }
    async with get_session() as session:
        stmt = pg_insert(FlightSearchDemandRow.__table__).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_flight_search_demand_route_date",
            set_={
                "priority": func.greatest(
                    FlightSearchDemandRow.priority, stmt.excluded.priority
                ),
                "source": stmt.excluded.source,
                "last_requested_at": now,
                "next_run_at": func.least(FlightSearchDemandRow.next_run_at, now),
                "expires_at": now + timedelta(days=7),
                "active": True,
            },
        )
        await session.execute(stmt)
        await session.commit()

async def claim_due_demands(limit):
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        await session.execute(
            update(FlightSearchDemandRow)
            .where(FlightSearchDemandRow.depart_date <= now.date().isoformat())
            .values(active=False)
        )
        rows = (await session.execute(
            select(FlightSearchDemandRow)
            .where(
                FlightSearchDemandRow.active.is_(True),
                FlightSearchDemandRow.expires_at > now,
                FlightSearchDemandRow.next_run_at <= now,
            )
            .order_by(
                FlightSearchDemandRow.priority.desc(),
                FlightSearchDemandRow.last_requested_at.desc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )).scalars().all()
        for row in rows:
            row.next_run_at = now + timedelta(hours=1)
        await session.commit()
        return [FlightSearchDemand.from_row(row) for row in rows]
~~~

- [ ] **Step 5: Extend snapshot persistence**

Add `data_provider`, `currency`, `price_status`, and `expires_at` to `PlatformPriceSnapshot`. Implement `upsert_provider_flights` using the existing itinerary ID and advisory transaction lock. Delete child rows only where both `flight_snapshot_id == sid` and `data_provider == provider`, then insert deterministic child IDs derived from `sid|provider|platform`. Set child expiry to `now + ttl_minutes`.

Implement `read_provider_deals` to filter child rows by Provider and return:

~~~python
(deals, newest_cache_age_seconds, all_provider_rows_are_stale)
~~~

Do not change the existing `read_deals` signature or its legacy behavior.

- [ ] **Step 6: Add the online Ctrip snapshot adapter**

~~~python
class CtripSnapshotProvider:
    name = "ctrip"

    def supports(self, query):
        return True

    async def search(self, query):
        rows, age, stale = await read_provider_deals(
            provider="ctrip_snapshot",
            origin_code=query.origin_code,
            destination_code=query.destination_code,
            depart_date=query.depart_date,
        )
        if not rows:
            await enqueue_demand(
                origin_code=query.origin_code,
                destination_code=query.destination_code,
                depart_date=query.depart_date,
                priority=50,
                source="recent_search",
            )
            return ProviderResult(
                provider=self.name, status=ProviderStatus.queued,
                message="等待下次刷新",
            )
        offers = ctrip_rows_to_offers(rows, query, stale=stale)
        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.stale if stale else ProviderStatus.success,
            offers=offers,
            cache_age_seconds=age,
        )
~~~

`ctrip_rows_to_offers` sets visible seller “携程”, `data_provider="ctrip_snapshot"`, unknown fees to `None`, `is_realtime=False`, and `PriceStatus.stale` for expired rows.

- [ ] **Step 7: Migrate, verify, and commit**

~~~bash
DATABASE_URL="$TEST_DATABASE_URL" alembic -c backend/alembic.ini upgrade head
pytest backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py backend/tests/infra/test_ctrip_snapshot_provider.py backend/tests/test_alembic_head.py -v
~~~

Expected: one Alembic head and all selected tests pass.

~~~bash
git add backend/db/migrations/versions/20260716_provider_snapshots.py backend/infrastructure/db/flight_demand_repo.py backend/infrastructure/db/flight_snapshot_repo.py backend/infrastructure/flight_data/providers/ctrip_snapshot.py backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py backend/tests/infra/test_ctrip_snapshot_provider.py
git commit -m "feat(flights): add Ctrip demand queue and snapshots"
~~~

---

### Task 5: Hourly Ctrip Worker with Lease

**Files:**
- Create: `backend/workers/ctrip_refresh.py`
- Modify: `backend/data_sources/ctrip_source.py`
- Modify: `backend/infrastructure/db/flight_demand_repo.py`
- Modify: `backend/infrastructure/db/alert_repo.py`
- Modify: `backend/workers/scheduler.py`
- Modify: `backend/workers/run_all.py`
- Modify: `backend/main.py`
- Create test: `backend/tests/workers/test_ctrip_refresh.py`
- Modify tests: `backend/tests/workers/test_scheduler.py`, `backend/tests/test_ctrip_source.py`, `backend/tests/test_lifespan.py`

**Interfaces:**
- Produces `refresh_ctrip_once() -> CtripRefreshSummary`.
- External worker owns cron job `ctrip_hourly_refresh` at minute 0.
- API does not start the browser scheduler when `RUN_SCHEDULER_IN_API=false`.

- [ ] **Step 1: Write failing worker tests**

~~~python
@pytest.mark.asyncio
async def test_refresh_persists_real_ctrip_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        fake_one_demand,
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: FakeRealCtripSource(),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.upsert_provider_flights",
        lambda provider, rows, ttl_minutes: record_async(
            calls, provider, rows, ttl_minutes
        ),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease",
        fake_acquired_lease,
    )
    summary = await refresh_ctrip_once()
    assert summary.processed == 1
    assert calls[0][0] == "ctrip_snapshot"
    assert calls[0][2] == 75

@pytest.mark.asyncio
async def test_overlap_skips_browser(monkeypatch):
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease",
        fake_rejected_lease,
    )
    summary = await refresh_ctrip_once()
    assert summary.skipped_overlap is True
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/workers/test_ctrip_refresh.py backend/tests/workers/test_scheduler.py -v
~~~

Expected: import failure for `ctrip_refresh.py`.

- [ ] **Step 3: Remove fabricated fields from real Ctrip normalization**

Change `CtripSource._normalize` so real results contain only a Ctrip seller row:

~~~python
"platform": "携程",
"price": price,
"tax": None,
"baggage_fee": None,
"has_baggage": None,
"prices": [{
    "platform": "携程",
    "price": price,
    "url": str(item.get("url") or item.get("jump_url") or ""),
}],
"booking_url": str(item.get("url") or item.get("jump_url") or "") or None,
~~~

Delete fabricated Qunar/FlyAI comparison rows. The worker always constructs `CtripSource(enable_mock_fallback=False, headless=True)`.

- [ ] **Step 4: Add a connection-scoped worker lease**

~~~python
@asynccontextmanager
async def try_ctrip_worker_lease():
    async with get_session() as session:
        acquired = bool(
            await session.scalar(select(func.pg_try_advisory_lock(731_640_175)))
        )
        try:
            yield acquired
        finally:
            if acquired:
                await session.execute(
                    select(func.pg_advisory_unlock(731_640_175))
                )
~~~

- [ ] **Step 5: Implement one refresh batch**

~~~python
@dataclass(frozen=True)
class CtripRefreshSummary:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped_overlap: bool = False

async def refresh_ctrip_once():
    async with try_ctrip_worker_lease() as acquired:
        if not acquired:
            return CtripRefreshSummary(skipped_overlap=True)
        await seed_ctrip_demands()
        demands = await claim_due_demands(settings.ctrip_refresh_batch_size)
        source = CtripSource(enable_mock_fallback=False, headless=True)
        succeeded = failed = 0
        for demand in demands:
            try:
                rows = await source.search_flights(
                    demand.origin_code, demand.destination_code,
                    demand.depart_date, demand.depart_date,
                )
                if rows:
                    await upsert_provider_flights(
                        "ctrip_snapshot", rows,
                        ttl_minutes=settings.ctrip_snapshot_ttl_minutes,
                    )
                succeeded += 1
            except Exception:
                failed += 1
            await asyncio.sleep(random.uniform(
                settings.ctrip_request_delay_min_seconds,
                settings.ctrip_request_delay_max_seconds,
            ))
        return CtripRefreshSummary(
            processed=len(demands), succeeded=succeeded, failed=failed,
        )
~~~

- [ ] **Step 6: Seed alert, recent-search, and hot-route priorities**

Add to `alert_repo.py`:

~~~python
async def list_active_alert_routes():
    async with get_session() as session:
        rows = (await session.execute(
            select(
                PriceAlert.origin,
                PriceAlert.destination,
                PriceAlert.depart_date,
            ).where(PriceAlert.status == "active")
        )).all()
        return [(row.origin, row.destination, row.depart_date) for row in rows]
~~~

Add to `ctrip_refresh.py`:

~~~python
async def seed_ctrip_demands():
    for origin, destination, depart_date in await list_active_alert_routes():
        origin_ref = resolve_airport(origin)
        destination_ref = resolve_airport(destination)
        if origin_ref is None or destination_ref is None:
            continue
        await enqueue_demand(
            origin_code=origin_ref.code,
            destination_code=destination_ref.code,
            depart_date=depart_date,
            priority=100,
            source="price_alert",
        )
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    for origin, destination in HOT_ROUTES:
        for offset in range(1, 4):
            await enqueue_demand(
                origin_code=origin,
                destination_code=destination,
                depart_date=(today + timedelta(days=offset)).isoformat(),
                priority=5,
                source="hot_route",
            )
~~~

Recent searches are already enqueued by `CtripSnapshotProvider` with priority 50. Add tests proving claim order is price alert (100), recent search (50), then hot route (5).

- [ ] **Step 7: Move scheduling out of FastAPI**

`build_scheduler` registers:

~~~python
scheduler.add_job(
    refresh_ctrip_once, trigger="cron", minute=0,
    id="ctrip_hourly_refresh", max_instances=1, coalesce=True,
)
~~~

In `main.py` start/shutdown a scheduler only if `settings.run_scheduler_in_api` is true; otherwise set `app.state.scheduler = None`. `backend.workers.run_all` remains the external owner and keeps the 15-minute alert job.

- [ ] **Step 8: Verify and commit**

~~~bash
pytest backend/tests/workers/test_ctrip_refresh.py backend/tests/workers/test_scheduler.py backend/tests/test_ctrip_source.py backend/tests/test_lifespan.py backend/tests/test_health_full.py -v
~~~

Expected: all selected tests pass; scheduler uses `max_instances=1`. Worker tests monkeypatch `asyncio.sleep` and assert every processed demand receives a delay within the configured 2–5 second range. Demand tests assert past dates become inactive and are never claimed.

~~~bash
git add backend/workers/ctrip_refresh.py backend/data_sources/ctrip_source.py backend/infrastructure/db/flight_demand_repo.py backend/infrastructure/db/alert_repo.py backend/workers/scheduler.py backend/workers/run_all.py backend/main.py backend/tests/workers/test_ctrip_refresh.py backend/tests/workers/test_scheduler.py backend/tests/test_ctrip_source.py backend/tests/test_lifespan.py
git commit -m "feat(worker): refresh Ctrip snapshots hourly"
~~~

---

### Task 6: Concurrent Aggregator and Production Search Tool

**Files:**
- Create: `backend/application/services/search_events.py`
- Create: `backend/application/services/flight_offer_normalizer.py`
- Create: `backend/application/services/flight_search_aggregator.py`
- Create: `backend/infrastructure/flight_data/providers/factory.py`
- Modify: `backend/resilience/circuit_breaker.py`
- Modify: `backend/application/graph/tools/search_flights.py`
- Modify: `backend/application/graph/nodes/render_response.py`
- Create tests: `backend/tests/services/test_flight_offer_normalizer.py`, `backend/tests/services/test_flight_search_aggregator.py`
- Modify test: `backend/tests/graph/tools/test_search_flights.py`
- Modify test: `backend/tests/graph/nodes/test_render_response.py`
- Modify test: `backend/tests/test_resilience.py`

**Interfaces:**
- Produces `SearchEventEmitter`, `bind_search_event_emitter`, and `emit_search_event`.
- Produces `FlightSearchAggregator.collect(query) -> dict`.
- Preserves LangChain tool name and three arguments.

- [ ] **Step 1: Write failing aggregation tests**

~~~python
@pytest.mark.asyncio
async def test_partial_success_survives_other_error():
    query = build_flight_query("北京", "上海", "2099-08-01")
    flyai = FakeProvider("flyai", ProviderResult(
        provider="flyai", status=ProviderStatus.success,
        offers=[make_offer(provider="flyai", seller="飞猪", price=580)],
    ))
    ctrip = FakeProvider("ctrip", ProviderResult(
        provider="ctrip", status=ProviderStatus.error, error_code="upstream",
    ))
    result = await FlightSearchAggregator(
        [flyai, ctrip], timeout_seconds=0.2
    ).collect(query)
    assert result["deals"][0]["price"] == 580
    assert result["provider_statuses"]["ctrip"] == "error"

@pytest.mark.asyncio
async def test_timeout_does_not_block_fast_result():
    result = await FlightSearchAggregator(
        [SlowProvider()], timeout_seconds=0.01
    ).collect(build_flight_query("北京", "上海", "2099-08-01"))
    assert result["provider_statuses"]["slow"] == "timeout"
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/services/test_flight_offer_normalizer.py backend/tests/services/test_flight_search_aggregator.py -v
~~~

Expected: import failure for the new service modules.

- [ ] **Step 3: Implement request-scoped event emission**

~~~python
@dataclass
class SearchEventEmitter:
    search_id: str
    sink: Callable[[dict], None]
    sequence: int = field(default=0, init=False)

    def emit(self, event_type, payload):
        self.sequence += 1
        self.sink({
            "type": event_type, "search_id": self.search_id,
            "sequence": self.sequence, "payload": payload,
        })

_EMITTER = ContextVar("search_event_emitter", default=None)

@contextmanager
def bind_search_event_emitter(emitter):
    token = _EMITTER.set(emitter)
    try:
        yield
    finally:
        _EMITTER.reset(token)

def emit_search_event(event_type, payload):
    emitter = _EMITTER.get()
    if emitter is not None:
        emitter.emit(event_type, payload)
~~~

- [ ] **Step 4: Implement offer normalization**

`offers_to_deals` deduplicates by flight number, date, departure time, and route. Each price row is:

~~~python
{
    "name": offer.seller_name,
    "price": offer.total_price,
    "lowest": False,
    "status": offer.price_status.value,
    "url": offer.booking_url,
    "data_provider": offer.data_provider,
}
~~~

Only the cheapest non-stale numeric row receives `lowest=True`. Missing-price and stale rows never win. Unknown fee values remain `None`. Price rows use `{"ctrip_snapshot": 0, "flyai": 1, "serpapi_google_flights": 2}` as stable display priority, with international sellers sharing priority 2 and then sorting by numeric price. `offers_to_deals` returns deduplicated unsorted cards; `rank_deals(deals)` sorts cards by real-time numeric total, stops, then departure time. Add one status row for Providers without offers so the UI can show loading/queued/timeout/error.

- [ ] **Step 5: Implement concurrent collection**

Create one task per applicable Provider. Each task uses `asyncio.wait_for(provider.search(query), timeout=10)`. Emit `started` and initial loading statuses, then a `provider_status` and full `results` snapshot after every completion. Cancel unfinished tasks in `finally`.

Return:

~~~python
{
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
~~~

- [ ] **Step 6: Add non-blocking short-term circuit breakers**

Refactor the existing `CircuitBreaker.call` so its lock protects state transitions only and is released before awaiting the Provider operation. Add a `_half_open_in_flight` flag so only one probe runs after recovery timeout. Configure one process-wide breaker per Provider with `failure_threshold=3` and `recovery_timeout=30.0` seconds.

Aggregator behavior:

~~~python
try:
    result = await breaker.call(provider.search, query)
except CircuitOpenError:
    result = ProviderResult(
        provider=provider.name,
        status=ProviderStatus.error,
        error_code="circuit_open",
        message="来源暂时熔断",
    )
~~~

Add a concurrency test proving two healthy closed-state calls can overlap, plus tests proving three consecutive failures open the circuit and a successful half-open probe resets it.

- [ ] **Step 7: Build Providers and replace tool fallback chain**

Factory order is FlyAI, Ctrip snapshot, SerpAPI. SerpAPI `supports` excludes mainland domestic routes.

Replace tool body:

~~~python
@tool
async def search_flights(origin: str, destination: str, depart_date: str) -> dict:
    try:
        query = build_flight_query(origin, destination, depart_date)
    except FlightQueryValidationError as exc:
        emit_search_event("validation_error", {"message": str(exc)})
        return {
            "deals": [], "source": "validation_error",
            "provider_statuses": {}, "validation_error": str(exc),
        }
    aggregator = FlightSearchAggregator(
        build_flight_providers(),
        timeout_seconds=settings.flight_provider_timeout_seconds,
    )
    return await aggregator.collect(query)
~~~

Remove cache/VariFlight/mock fare fallbacks from this tool only. Do not delete those modules.

- [ ] **Step 8: Render empty, disabled, and failed states distinctly**

In `render_response.py` change the default `result_source` from `mock` to `none`. When `search_result` is a dict and no deals exist, choose deterministic copy before considering the last LLM message:

~~~python
def _empty_search_text(search_result):
    validation = search_result.get("validation_error")
    if validation:
        return validation
    statuses = list((search_result.get("provider_statuses") or {}).values())
    if statuses and all(status == "disabled" for status in statuses):
        return "机票数据源尚未配置，请联系管理员完成配置。"
    if statuses and all(status == "empty" for status in statuses):
        return "当前日期和航线暂无可售结果，可以换个日期再试。"
    if statuses and all(
        status in {"error", "timeout", "disabled"} for status in statuses
    ):
        return "机票数据暂时不可用，请稍后重试。"
    return "暂时没有找到符合条件的航班，可以换个日期或路线再试。"
~~~

Explicit validation/configuration/provider-failure messages must not be overwritten by `_last_ai_text`. Add one render test for each branch.

- [ ] **Step 9: Verify and commit**

~~~bash
pytest backend/tests/services/test_flight_offer_normalizer.py backend/tests/services/test_flight_search_aggregator.py backend/tests/graph/tools/test_search_flights.py backend/tests/graph/nodes/test_render_response.py backend/tests/graph/test_search_graph.py backend/tests/test_resilience.py -v
~~~

Expected: all tests pass and no test expects `mock_fallback`.

~~~bash
git add backend/application/services/search_events.py backend/application/services/flight_offer_normalizer.py backend/application/services/flight_search_aggregator.py backend/infrastructure/flight_data/providers/factory.py backend/resilience/circuit_breaker.py backend/application/graph/tools/search_flights.py backend/application/graph/nodes/render_response.py backend/tests/services/test_flight_offer_normalizer.py backend/tests/services/test_flight_search_aggregator.py backend/tests/graph/tools/test_search_flights.py backend/tests/graph/nodes/test_render_response.py backend/tests/test_resilience.py
git commit -m "feat(flights): aggregate real providers concurrently"
~~~

---

### Task 7: Backward-Compatible NDJSON Search API

**Files:**
- Modify: `backend/api/search.py`
- Create test: `backend/tests/api/test_search_stream.py`
- Modify test: `backend/tests/api/test_search.py`

**Interfaces:**
- Preserves `POST /api/search -> FrontendResponse`.
- Produces `POST /api/search/stream -> application/x-ndjson`.
- Final `complete` payload contains the same `FrontendResponse` contract.

- [ ] **Step 1: Write failing endpoint tests**

~~~python
class FakeGraph:
    async def ainvoke(self, state, config=None):
        emit_search_event("started", {"providers": ["flyai", "ctrip"]})
        emit_search_event(
            "provider_status", {"provider": "flyai", "status": "loading"}
        )
        emit_search_event("results", {"deals": [{"price": 580}]})
        return {
            **state,
            "request_session_id": "s_stream",
            "response": FrontendResponse(
                user_id=state["request_user_id"],
                session_id="s_stream",
                deals=[{"price": 580}],
                analysis={},
                recommendation={"text": "找到结果"},
                meta={},
            ),
        }

@pytest.mark.asyncio
async def test_stream_requires_auth(client):
    response = await client.post(
        "/api/search/stream",
        json={"session_id": None, "message": "北京到上海"},
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_stream_emits_ordered_ndjson(
    client, valid_jwt_for_u1, monkeypatch,
):
    monkeypatch.setattr("backend.api.search.get_graph", lambda: FakeGraph())
    response = await client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert events[-1]["type"] == "complete"
    assert events[-1]["payload"]["response"]["session_id"] == "s_stream"
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/api/test_search_stream.py -v
~~~

Expected: `404` for `/api/search/stream`.

- [ ] **Step 3: Extract one graph invocation helper**

~~~python
async def _invoke_graph(req, request, uid, request_id):
    graph = get_graph()
    out = await graph.ainvoke(
        {
            "request_id": request_id,
            "request_user_id": uid,
            "request_session_id": req.session_id,
            "request_message": req.message,
            "messages": [HumanMessage(content=req.message)],
            "clarify_count": 0,
            "fallback_triggered": False,
            "errors": [],
            "_session_factory": getattr(
                request.app.state, "session_factory", None
            ),
            "_redis_client": getattr(
                request.app.state, "redis_client", None
            ),
        },
        config={"recursion_limit": 15},
    )
    response = out["response"]
    response.session_id = out.get("request_session_id")
    emit_search_event(
        "complete",
        {"response": response.model_dump(mode="json")},
    )
    return response
~~~

The old endpoint calls this helper and retains existing logging.

- [ ] **Step 4: Add NDJSON streaming with cleanup**

~~~python
@router.post("/stream")
async def search_stream(
    req: SearchReq,
    request: Request,
    uid: str = Depends(current_user_id),
):
    request_id = uuid.uuid4().hex
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    emitter = SearchEventEmitter(request_id, queue.put_nowait)

    async def run_graph():
        try:
            with bind_search_event_emitter(emitter):
                await _invoke_graph(
                    req, request, uid, request_id
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "search_stream_failed request_id=%s", request_id
            )
            emitter.emit(
                "complete",
                {
                    "error": "search_failed",
                    "message": "搜索暂时不可用，请稍后重试",
                },
            )
        finally:
            queue.put_nowait(None)

    async def body():
        task = asyncio.create_task(run_graph())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
~~~

- [ ] **Step 5: Test disconnect cleanup**

Use a fake graph that waits indefinitely, consume the first event, close the response, and assert the graph receives `CancelledError`.

- [ ] **Step 6: Verify and commit**

~~~bash
pytest backend/tests/api/test_search.py backend/tests/api/test_search_stream.py -v
~~~

Expected: legacy JSON and NDJSON tests pass.

~~~bash
git add backend/api/search.py backend/tests/api/test_search.py backend/tests/api/test_search_stream.py
git commit -m "feat(api): stream progressive flight search results"
~~~

---

### Task 8: Frontend Stream Client and Nullable Types

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/mappers.ts`
- Modify tests: `frontend/__tests__/api.test.ts`, `frontend/__tests__/mappers.test.ts`

**Interfaces:**
- Produces `searchApi.stream(body, onEvent, signal?) -> Promise<ChatSearchResponse | null>`.
- Existing `searchApi.search` remains available.

- [ ] **Step 1: Write failing chunk-boundary test**

~~~typescript
test("stream parses NDJSON across chunk boundaries", async () => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode('{"type":"started","search_id":"x",')
      );
      controller.enqueue(
        encoder.encode('"sequence":1,"payload":{}}\n')
      );
      controller.enqueue(
        encoder.encode(
          '{"type":"complete","search_id":"x","sequence":2,' +
          '"payload":{"response":{"session_id":"s1","deals":[]}}}\n'
        )
      );
      controller.close();
    },
  });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(stream, {
      status: 200,
      headers: { "content-type": "application/x-ndjson" },
    })
  );
  const events: SearchStreamEvent[] = [];
  const response = await searchApi.stream(
    { session_id: null, message: "北京到上海" },
    (event) => events.push(event),
  );
  expect(events.map((event) => event.type)).toEqual(
    ["started", "complete"]
  );
  expect(response?.session_id).toBe("s1");
});
~~~

Add a mapper test proving `null` price/tax/baggage fields stay `null`.

- [ ] **Step 2: Verify failure**

~~~bash
npm --prefix frontend test -- --run __tests__/api.test.ts __tests__/mappers.test.ts
~~~

Expected: missing `searchApi.stream` and nullable type failures.

- [ ] **Step 3: Align TypeScript types**

~~~typescript
export type ProviderDisplayStatus =
  | "loading" | "queued" | "success" | "empty" | "stale"
  | "timeout" | "disabled" | "error" | "view_live_price";

export interface PriceItem {
  name: string;
  price: number | null;
  lowest?: boolean;
  status: ProviderDisplayStatus;
  url?: string | null;
  data_provider?: string | null;
}

export interface SearchStreamEvent {
  type:
    | "started" | "provider_status" | "results"
    | "validation_error" | "complete";
  search_id: string;
  sequence: number;
  payload: {
    response?: ChatSearchResponse;
    deals?: DealCardDto[];
    provider?: string;
    status?: ProviderDisplayStatus;
    message?: string;
    [key: string]: unknown;
  };
}
~~~

Make `DealCardDto.price`, `tax`, `baggage_fee`, and `has_baggage` nullable. Add `total_price` and `currency`.

- [ ] **Step 4: Implement authenticated NDJSON reading**

Extract auth/401 retry into `requestWithSession`, then implement:

~~~typescript
async function readNdjson(
  response: Response,
  onEvent: (event: SearchStreamEvent) => void,
): Promise<ChatSearchResponse | null> {
  if (!response.body) throw new Error("stream body missing");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatSearchResponse | null = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line) as SearchStreamEvent;
      onEvent(event);
      if (
        event.type === "complete" &&
        event.payload.response
      ) {
        finalResponse = event.payload.response;
      }
    }
    if (done) break;
  }
  if (buffer.trim()) {
    const event = JSON.parse(buffer) as SearchStreamEvent;
    onEvent(event);
    if (event.type === "complete" && event.payload.response) {
      finalResponse = event.payload.response;
    }
  }
  return finalResponse;
}
~~~

Add `searchApi.stream`:

~~~typescript
stream: async (body, onEvent, signal) => {
  const response = await requestWithSession("/api/search/stream", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
  return readNdjson(response, onEvent);
}
~~~

- [ ] **Step 5: Add 401 and malformed-line tests**

First response 401 then a successful stream must refresh the session once. Malformed JSON must reject instead of silently completing.

- [ ] **Step 6: Verify and commit**

~~~bash
npm --prefix frontend test -- --run __tests__/api.test.ts __tests__/mappers.test.ts
npm --prefix frontend run lint
~~~

Expected: tests and TypeScript pass.

~~~bash
git add frontend/lib/api.ts frontend/lib/mappers.ts frontend/__tests__/api.test.ts frontend/__tests__/mappers.test.ts
git commit -m "feat(frontend): add progressive search stream client"
~~~

---

### Task 9: Progressive Existing Card UI

**Files:**
- Modify: `frontend/components/discovery-card-content.tsx`
- Modify: `frontend/components/chat-page.tsx`
- Modify test: `frontend/__tests__/component-chat-page.test.tsx`
- Create test: `frontend/__tests__/discovery-card-content.test.tsx`

**Interfaces:**
- Renders loading, queued, stale, timeout, disabled, error, empty, and live-price states.
- Only the newest active search may update its message.

- [ ] **Step 1: Write failing card-state test**

~~~typescript
test("renders source states without fake zeroes", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={null}
      totalPrice={null}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      platform="飞猪"
      prices={[
        {
          name: "飞猪",
          price: null,
          status: "view_live_price",
          url: "https://fly.test",
        },
        { name: "携程", price: null, status: "loading" },
      ]}
    />
  );
  expect(screen.getByText("查看实时价")).toHaveAttribute(
    "href", "https://fly.test"
  );
  expect(screen.getByText("正在获取数据")).toBeInTheDocument();
  expect(screen.getByText("行李额以预订页为准")).toBeInTheDocument();
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
});
~~~

Update the chat test mock so `searchApi.stream` emits `started`, `results`, then `complete`. Assert the card appears when `results` fires, before the stream Promise resolves.

- [ ] **Step 2: Verify failure**

~~~bash
npm --prefix frontend test -- --run __tests__/discovery-card-content.test.tsx __tests__/component-chat-page.test.tsx
~~~

Expected: numeric-only card and non-streaming chat fail.

- [ ] **Step 3: Render nullable totals and statuses**

Change props:

~~~typescript
basePrice: number | null;
totalPrice?: number | null;
tax: number | null;
baggageFee: number | null;
hasBaggage: boolean | null;
~~~

Use ordinary string concatenation so null can never become zero:

~~~typescript
const computedTotal =
  totalPrice ??
  (
    basePrice !== null &&
    tax !== null &&
    baggageFee !== null
      ? basePrice + tax + baggageFee
      : null
  );
const money = (value: number | null) =>
  value === null ? "待确认" : "¥" + value;
~~~

Status labels:

~~~typescript
const statusText = {
  loading: "正在获取数据",
  queued: "等待下次刷新",
  stale: "价格可能已更新",
  timeout: "暂时超时",
  disabled: "尚未配置",
  error: "暂时不可用",
  empty: "暂无结果",
} satisfies Partial<Record<ProviderDisplayStatus, string>>;
~~~

Render `view_live_price` as “查看实时价” only for an HTTPS URL. Show “最低” only when `lowest === true`. Unknown baggage displays “行李额以预订页为准”.

- [ ] **Step 4: Consume events in the existing rich chat**

Give messages stable IDs and each send a client search ID. Keep one `AbortController`. On `results`, map `payload.deals[0]` and update the same assistant message. On `complete`, apply final recommendation and replace remaining `loading` rows with terminal states. On `validation_error`, remove the spinner and show the validation message.

Reject stale events:

~~~typescript
if (activeSearchRef.current !== clientSearchId) return;
~~~

Abort the previous request before a new search and abort on unmount.

- [ ] **Step 5: Verify all frontend behavior**

~~~bash
npm --prefix frontend test -- --run __tests__/discovery-card-content.test.tsx __tests__/component-chat-page.test.tsx
npm --prefix frontend run lint
npm --prefix frontend test
~~~

Expected: focused tests, lint, and full frontend suite pass.

- [ ] **Step 6: Commit**

~~~bash
git add frontend/components/discovery-card-content.tsx frontend/components/chat-page.tsx frontend/__tests__/component-chat-page.test.tsx frontend/__tests__/discovery-card-content.test.tsx
git commit -m "feat(frontend): progressively update fare cards"
~~~

---

### Task 10: Provider-Level LangSmith Tracing and Redaction

**Files:**
- Create: `backend/infrastructure/observability/provider_tracing.py`
- Modify: `backend/application/services/flight_search_aggregator.py`
- Modify: `backend/api/search.py`
- Modify: `backend/workers/ctrip_refresh.py`
- Create test: `backend/tests/observability/test_provider_tracing.py`
- Modify tests: `backend/tests/services/test_flight_search_aggregator.py`, `backend/tests/workers/test_ctrip_refresh.py`

**Interfaces:**
- Produces `trace_provider_call(provider, query, operation) -> ProviderResult`.
- Produces `trace_flight_search(request_id, message_length, operation) -> FrontendResponse`.
- Produces `trace_stage(name, inputs, operation)` for standardization and ranking.
- Produces `trace_ctrip_refresh(operation) -> CtripRefreshSummary`.
- Inputs contain route/date only; outputs contain status/count/latency only.

- [ ] **Step 1: Write failing redaction tests**

~~~python
def test_trace_inputs_exclude_secrets():
    inputs = safe_provider_inputs(
        provider="flyai", origin_code="BJS",
        destination_code="SHA", depart_date="2099-08-01",
    )
    text = repr(inputs)
    assert "FLYAI_API_KEY" not in text
    assert "api_key" not in text.lower()

def test_trace_output_is_summary_not_offer():
    assert safe_provider_outputs(
        status="success", offer_count=3,
        latency_ms=420, cache_age_seconds=None,
    ) == {
        "status": "success",
        "offer_count": 3,
        "latency_ms": 420,
        "cache_age_seconds": None,
    }
~~~

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/observability/test_provider_tracing.py -v
~~~

Expected: import failure for `provider_tracing.py`.

- [ ] **Step 3: Add safe trace wrappers**

~~~python
from langsmith import trace

def safe_provider_inputs(
    *, provider, origin_code, destination_code, depart_date,
):
    return {
        "provider": provider,
        "origin_code": origin_code,
        "destination_code": destination_code,
        "depart_date": depart_date,
    }

def safe_provider_outputs(
    *, status, offer_count, latency_ms, cache_age_seconds,
):
    return {
        "status": status,
        "offer_count": offer_count,
        "latency_ms": latency_ms,
        "cache_age_seconds": cache_age_seconds,
    }

async def trace_provider_call(provider, query, operation):
    with trace(
        name=f"provider.{provider}",
        run_type="tool",
        inputs=safe_provider_inputs(
            provider=provider,
            origin_code=query.origin_code,
            destination_code=query.destination_code,
            depart_date=query.depart_date,
        ),
    ) as run:
        result = await operation()
        run.end(outputs=safe_provider_outputs(
            status=result.status.value,
            offer_count=len(result.offers),
            latency_ms=result.latency_ms,
            cache_age_seconds=result.cache_age_seconds,
        ))
        return result

def trace_stage(name, inputs, operation):
    with trace(name=name, run_type="chain", inputs=inputs) as run:
        output = operation()
        run.end(outputs={"result_count": len(output)})
        return output

async def trace_flight_search(request_id, message_length, operation):
    with trace(
        name="flight_search",
        run_type="chain",
        inputs={
            "request_id": request_id,
            "message_length": message_length,
        },
    ) as run:
        response = await operation()
        with trace(
            name="stream_results",
            run_type="chain",
            inputs={"request_id": request_id},
        ) as stream_run:
            emit_search_event(
                "complete",
                {"response": response.model_dump(mode="json")},
            )
            stream_run.end(outputs={"event_type": "complete"})
        run.end(outputs={
            "deal_count": len(response.deals),
            "has_recommendation": bool(response.recommendation),
        })
        return response

async def trace_ctrip_refresh(operation):
    with trace(
        name="ctrip_hourly_refresh",
        run_type="chain",
        inputs={"schedule": "hourly"},
    ) as run:
        summary = await operation()
        run.end(outputs={
            "processed": summary.processed,
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "skipped_overlap": summary.skipped_overlap,
        })
        return summary
~~~

- [ ] **Step 4: Wrap Provider tasks and worker batch**

Aggregator task body:

~~~python
result = await asyncio.wait_for(
    trace_provider_call(
        provider.name,
        query,
        lambda: provider.search(query),
    ),
    timeout=self._timeout_seconds,
)
~~~

Split worker into private `_refresh_ctrip_once` and public:

~~~python
async def refresh_ctrip_once():
    return await trace_ctrip_refresh(_refresh_ctrip_once)
~~~

Do not decorate Provider instance methods because serializers could inspect instance fields containing keys.

Wrap `graph.ainvoke` inside `_invoke_graph` with `trace_flight_search`. Remove the direct `complete` emission added in Task 7 because the trace wrapper now owns that final event. In the aggregator, call `trace_stage("normalize_and_deduplicate", ...)` around `offers_to_deals` and `trace_stage("rank_results", ...)` around `rank_deals`. These calls execute inside the `flight_search` context, so Provider and stage runs appear beneath the root Trace.

- [ ] **Step 5: Verify and commit**

~~~bash
pytest backend/tests/observability/test_provider_tracing.py backend/tests/services/test_flight_search_aggregator.py backend/tests/workers/test_ctrip_refresh.py backend/tests/observability backend/tests/test_health_full.py -v
~~~

Expected: tests pass and mocked traces contain no secrets or raw offers.

~~~bash
git add backend/infrastructure/observability/provider_tracing.py backend/application/services/flight_search_aggregator.py backend/api/search.py backend/workers/ctrip_refresh.py backend/tests/observability/test_provider_tracing.py backend/tests/services/test_flight_search_aggregator.py backend/tests/workers/test_ctrip_refresh.py
git commit -m "feat(observability): trace flight providers safely"
~~~

---

### Task 11: Railway Build, Environment Contract, and Smoke Verification

**Files:**
- Modify: `backend/nixpacks.toml`
- Modify: `backend/.env.example`
- Modify: `railway.toml`
- Modify: `docs/deployment/RAILWAY.md`
- Modify: `README.md`
- Modify: `frontend/components/app-shell.tsx`
- Create: `backend/scripts/verify_flight_providers.py`
- Modify tests: `backend/tests/test_dependency_manifest.py`, `backend/tests/test_railway_config.py`
- Create test: `backend/tests/scripts/test_verify_flight_providers.py`

**Interfaces:**
- Backend image contains Node 22 and FlyAI CLI 1.0.16.
- Smoke script prints Provider statuses/count/seller names only.

- [ ] **Step 1: Write failing deployment tests**

~~~python
def test_nixpacks_pins_flyai_cli_and_node():
    text = Path("backend/nixpacks.toml").read_text()
    assert "nodejs_22" in text
    assert "@fly-ai/flyai-cli@1.0.16" in text

def test_env_example_has_empty_provider_keys():
    text = Path("backend/.env.example").read_text()
    assert "\nFLYAI_API_KEY=\n" in "\n" + text
    assert "\nSERPAPI_API_KEY=\n" in "\n" + text
    assert "ENABLE_MOCK_FALLBACK=false" in text
~~~

Update Railway test to assert the worker command remains `python -m backend.workers.run_all` and backend migrates before starting.

- [ ] **Step 2: Verify failure**

~~~bash
pytest backend/tests/test_dependency_manifest.py backend/tests/test_railway_config.py -v
~~~

Expected: Node/FlyAI pin assertions fail.

- [ ] **Step 3: Pin build-time FlyAI runtime**

~~~toml
[phases.setup]
nixPkgs = ["chromium", "chromedriver", "nodejs_22"]

[phases.install]
cmds = [
  "pip install -r requirements.txt",
  "npm install -g @fly-ai/flyai-cli@1.0.16"
]
~~~

Never call `flyai config set` in the build. Runtime reads `FLYAI_API_KEY`.
Document that `npx skills add alibaba-flyai/flyai-skill` installs instructions for a compatible coding-agent host; FareSniper's Railway service is not such a host and therefore installs the official CLI directly. Local developers may install the skill separately, but it is not a production dependency.

- [ ] **Step 4: Update environment examples and deployment docs**

Add empty/config values:

~~~dotenv
ENABLE_MOCK_FALLBACK=false
FLYAI_API_KEY=
FLYAI_CLI_PATH=flyai
SERPAPI_API_KEY=
FLIGHT_PROVIDER_TIMEOUT_SECONDS=10
CTRIP_SNAPSHOT_TTL_MINUTES=75
CTRIP_REFRESH_BATCH_SIZE=20
RUN_SCHEDULER_IN_API=false
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
~~~

`docs/deployment/RAILWAY.md` must separate backend and worker variables, state that the worker owns hourly Ctrip collection, and include:

~~~bash
flyai --help
flyai search-flight --origin "北京" --destination "上海" --dep-date 2099-08-01 --sort-type 3
curl -N -X POST "https://<backend>/api/search/stream" \
  -H "Authorization: Bearer <session-token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":null,"message":"8月1日北京到上海"}'
~~~

Document that examples must be changed to a future date after expiry.

- [ ] **Step 5: Add safe smoke script**

`verify_flight_providers.py` accepts `--origin`, `--destination`, `--depart-date`, builds a query, runs the aggregator, and prints only:

~~~json
{
  "provider_statuses": {"flyai": "success", "ctrip": "queued"},
  "deal_count": 3,
  "sellers": ["飞猪", "携程"]
}
~~~

Test with a monkeypatched aggregator and assert a secret sentinel and complete booking URL are absent from stdout.

- [ ] **Step 6: Correct visible source claims**

In `frontend/components/app-shell.tsx` replace unsupported “5 大平台” and Qunar/Tongcheng/Umetrip claims with:

~~~text
携程、飞猪与国际航司/销售平台实时比价
~~~

Do not change layout, colors, spacing, or card composition.

- [ ] **Step 7: Run full verification**

~~~bash
git diff --check
DATABASE_URL="$TEST_DATABASE_URL" alembic -c backend/alembic.ini upgrade head
pytest
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
~~~

Expected: one Alembic head; backend tests, frontend lint/tests/build all pass; `git diff --check` is silent.

With keys configured, run:

~~~bash
python -m backend.scripts.verify_flight_providers --origin 北京 --destination 上海 --depart-date <future-date>
python -m backend.scripts.verify_flight_providers --origin 上海 --destination 新加坡 --depart-date <future-date>
~~~

Expected: JSON summaries contain statuses and seller names, with no secrets.

- [ ] **Step 8: Commit**

~~~bash
git add backend/nixpacks.toml backend/.env.example railway.toml docs/deployment/RAILWAY.md README.md frontend/components/app-shell.tsx backend/scripts/verify_flight_providers.py backend/tests/test_dependency_manifest.py backend/tests/test_railway_config.py backend/tests/scripts/test_verify_flight_providers.py
git commit -m "docs(deploy): configure real flight providers on Railway"
~~~

---

## Final Review Gate

1. Invoke `superpowers:verification-before-completion` and rerun Task 11 Step 7.
2. Invoke `superpowers:requesting-code-review` and review all commits against the approved design.
3. Scan for secrets:

~~~bash
git grep -nE 'lsv2_|sk-[A-Za-z0-9_-]{16,}|SERPAPI_API_KEY=.+|FLYAI_API_KEY=.+'
~~~

Expected: no real values.

4. Confirm mock fallback is disabled:

~~~bash
git grep -n "ENABLE_MOCK_FALLBACK"
~~~

Expected: default and deployment example are `false`.

5. Deploy backend, worker, then frontend. Verify one domestic and one international future-date search.
6. In LangSmith project `faresniper`, verify `flight_search` has applicable `provider.flyai`, `provider.ctrip`, and `provider.serpapi` child spans, and `ctrip_hourly_refresh` appears after the worker runs.

## Official References

- FlyAI repository and CLI: https://github.com/alibaba-flyai/flyai-skill
- FlyAI flight command: https://github.com/alibaba-flyai/flyai-skill/blob/main/skills/flyai/references/search-flight.md
- SerpAPI Google Flights: https://serpapi.com/google-flights-api
- SerpAPI booking options: https://serpapi.com/google-flights-booking-options
