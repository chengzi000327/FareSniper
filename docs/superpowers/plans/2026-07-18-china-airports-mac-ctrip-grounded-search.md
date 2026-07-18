# FareSniper China Airports, Mac Ctrip Collector, and Grounded Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide every Chinese commercial transport-airport city as a searchable location, collect real Ctrip China fares through a persistent Mac node, combine them with FlyAI and SerpAPI offers, and guarantee that AI text and FareSniper cards display the same prices.

**Architecture:** A checked-in, versioned `AirportCatalog` becomes the only city/airport resolver for mainland China, Hong Kong, Macau, and Taiwan. Railway stores provider-scoped snapshots and leases collection jobs to a token-authenticated Mac daemon that reuses a dedicated Ctrip Chrome profile; online search reads snapshots and concurrently calls configured real-time providers. A deterministic grounded-response renderer freezes final deals and produces every flight number, time, price, minimum-price statement, and budget comparison consumed by both the AI message and card UI.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, PostgreSQL, asyncio, httpx, Selenium 4 on macOS, Chrome, `launchd`, LangGraph, LangSmith, Next.js 15, React 19, TypeScript, Vitest, pytest.

## Global Constraints

- Scope is flights only; do not add hotels, payments, ticketing, changes, refunds, or order management.
- Include all mainland CAAC transport airports plus all Hong Kong, Macau, and Taiwan airports with commercial passenger service; exclude military, general-aviation-only, heliport, closed, and not-yet-operational airports from bookable locations.
- Runtime requests never download airport data; commit generated `backend/data/china_airports.json` with source metadata.
- Do not create every city-pair collection job; jobs come only from recent searches, active price alerts, and configured hot routes.
- Railway backend and worker processes must not launch Chrome or receive Ctrip cookies, passwords, or browser profiles.
- Mac collector uses a dedicated persistent profile and `--no-proxy-server`; it never bypasses CAPTCHA or fabricates device proof.
- `CTRIP_COLLECTOR_TOKEN`, `FLYAI_API_KEY`, `SERPAPI_API_KEY`, model keys, and LangSmith keys remain environment-only and must never be logged or committed.
- Ctrip failures and empty responses never delete the last successful snapshot.
- Unknown tax and baggage values remain `None`; never fabricate fixed tax, free baggage, other-platform prices, discounts, or confidence.
- Stale Ctrip display prices remain eligible for “平台展示价最低” and must show “价格可能已更新，以预订页为准”.
- Final ranked `deals` are the only source for cards, Markdown tables, price claims, budget claims, alert suggestions, and chat-history assistant text.
- A real-time provider timeout is 10 seconds; one provider failure never discards another provider success.
- Default test suites use fixtures only; real Ctrip, FlyAI, and SerpAPI calls require explicit verification commands.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/data/china_airports.json` | Generated runtime airport-city catalog with version metadata |
| `backend/data/china_airport_overrides.json` | Reviewed Chinese aliases, multi-airport codes, and HK/MO/TW additions |
| `backend/scripts/update_china_airports.py` | Deterministically merge CAAC, OurAirports, and overrides |
| `backend/application/services/airport_catalog.py` | Typed location resolution and provider-code conversion |
| `backend/application/contracts/flight_provider.py` | Provider query, offer, price, and status contracts |
| `backend/application/services/flight_query.py` | Validate date, resolve locations, and classify route region |
| `backend/infrastructure/flight_data/providers/` | FlyAI, SerpAPI, and Ctrip snapshot adapters |
| `backend/application/services/flight_search_aggregator.py` | Concurrent provider execution, normalization, dedupe, and snapshots |
| `backend/infrastructure/flight_data/ctrip_parser.py` | Pure parser for captured Ctrip `batchSearch` payloads |
| `backend/infrastructure/db/flight_demand_repo.py` | Collector demand, lease, heartbeat, and retry persistence |
| `backend/api/collector.py` | Token-authenticated claim, complete, fail, and heartbeat endpoints |
| `backend/collector/` | Mac-only client, browser session, runner, CLI, and diagnostics |
| `deploy/macos/com.faresniper.ctrip-collector.plist.template` | `launchd` agent template |
| `scripts/install_macos_collector.sh` | Mac virtualenv, configuration, login, and `launchd` installer |
| `backend/application/services/grounded_response.py` | Deterministic response facts, Markdown, and optional prose validation |
| `frontend/components/discovery-card-content.tsx` | Nullable fare components and provider states |
| `frontend/lib/api.ts` | Stream and nullable fare DTOs |

---

### Task 1: Versioned China Airport Catalog

**Files:**
- Create: `backend/data/china_airports.json`
- Create: `backend/data/china_airport_overrides.json`
- Create: `backend/scripts/update_china_airports.py`
- Create: `backend/application/services/airport_catalog.py`
- Modify: `backend/utils/airport_codes.py`
- Test: `backend/tests/services/test_airport_catalog.py`
- Test: `backend/tests/scripts/test_update_china_airports.py`
- Fixtures: `backend/tests/fixtures/airports/caac_airports.xlsx`, `backend/tests/fixtures/airports/ourairports_cn.csv`

**Interfaces:**
- Produces: `AirportCatalog.load_default() -> AirportCatalog`
- Produces: `resolve_location(text: str) -> ResolvedLocation | None`
- Produces: `city_to_provider_code(city_id: str, provider: str) -> str`
- Produces: `code_to_city(code: str) -> str`
- Produces JSON fields: `metadata`, `cities[]`, and nested `airports[]`.

- [ ] **Step 1: Write failing catalog coverage and resolution tests**

```python
def test_default_catalog_covers_all_regions():
    catalog = AirportCatalog.load_default()
    assert catalog.metadata.mainland_transport_airports >= 270
    assert {"mainland", "hong_kong", "macau", "taiwan"} <= {
        city.region_group for city in catalog.cities
    }

def test_multi_airport_and_specific_airport_resolution():
    catalog = AirportCatalog.load_default()
    assert catalog.resolve_location("北京").provider_code("ctrip") == "BJS"
    assert catalog.resolve_location("北京大兴机场").airport_iata == "PKX"
    assert catalog.resolve_location("PVG").city_name == "上海"
    assert catalog.resolve_location("香港").provider_code("ctrip") == "HKG"
    assert catalog.resolve_location("台北桃园机场").airport_iata == "TPE"

def test_no_duplicate_codes_or_non_bookable_airports():
    catalog = AirportCatalog.load_default()
    iata = [a.iata for c in catalog.cities for a in c.airports if a.iata]
    icao = [a.icao for c in catalog.cities for a in c.airports if a.icao]
    assert len(iata) == len(set(iata))
    assert len(icao) == len(set(icao))
    assert all(a.bookable for c in catalog.cities for a in c.airports)
```

- [ ] **Step 2: Run tests and verify missing-module/data failures**

Run: `.venv/bin/pytest backend/tests/services/test_airport_catalog.py backend/tests/scripts/test_update_china_airports.py -v`

Expected: FAIL because `airport_catalog.py` and catalog files do not exist.

- [ ] **Step 3: Implement deterministic catalog generator**

`update_china_airports.py` must accept explicit inputs so tests never use the network:

Implement exact entry points `build_catalog(*, caac_xlsx: Path, ourairports_csv: Path, overrides_json: Path) -> dict[str, Any]`, `validate_catalog(payload: dict[str, Any]) -> None`, and `main(argv: Sequence[str] | None = None) -> int`.

Filter OurAirports to `iso_country in {"CN", "HK", "MO", "TW"}`, non-empty IATA, active `large_airport|medium_airport|small_airport`, and scheduled passenger service. Merge mainland records against CAAC Chinese airport names; apply reviewed overrides for Chinese city aliases, provider city codes, multi-airport cities, and HK/MO/TW. Sort cities by `city_id` and airports by IATA before JSON serialization so regeneration is stable.

- [ ] **Step 4: Implement typed runtime resolver**

Define immutable `ResolvedLocation(city_id, city_name, region_group, city_codes, airport_iata=None, airport_icao=None)` with `provider_code(provider: str) -> str`. Define `AirportCatalog.load_default()`, `resolve_location(text)`, `resolve_city(text)`, `resolve_airport(text)`, and `code_to_city(code)` with the return types in the Interfaces block.

Normalize whitespace, `市`, `机场`, and ASCII code casing without fuzzy-guessing unrelated cities. Preserve an explicit airport constraint when the input names an airport. Keep `backend/utils/airport_codes.py` as a compatibility wrapper backed by the catalog.

- [ ] **Step 5: Generate and validate the checked-in full catalog**

Run:

```bash
.venv/bin/python -m backend.scripts.update_china_airports \
  --caac-xlsx tmp/sources/2025-caac-airports.xlsx \
  --ourairports-csv tmp/sources/ourairports-airports.csv \
  --overrides backend/data/china_airport_overrides.json \
  --output backend/data/china_airports.json
```

Expected: command reports the generated mainland transport-airport count, regional city counts, zero duplicate IATA/ICAO codes, and exits `0`.

- [ ] **Step 6: Run focused tests**

Run: `.venv/bin/pytest backend/tests/services/test_airport_catalog.py backend/tests/scripts/test_update_china_airports.py backend/tests/test_airport_mapping.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/data backend/scripts/update_china_airports.py backend/application/services/airport_catalog.py backend/utils/airport_codes.py backend/tests/services/test_airport_catalog.py backend/tests/scripts/test_update_china_airports.py backend/tests/fixtures/airports
git commit -m "feat(airports): add complete China airport catalog"
```

---

### Task 2: Migrate City Parsing and Provider Routing to the Catalog

**Files:**
- Modify: `backend/application/services/intent_slot_filler.py`
- Modify: `backend/services/intent_parser.py`
- Modify: `backend/third_party/flights_monitor/shared.py`
- Modify: `backend/infrastructure/flight_data/variflight_client.py`
- Modify: `backend/application/services/_routes.py`
- Modify: `backend/application/services/recommendation_service.py`
- Create: `backend/application/services/flight_query.py`
- Test: `backend/tests/services/test_flight_query.py`
- Modify tests: `backend/tests/services/test_intent_slot_filler.py`, `backend/tests/test_airport_mapping.py`, `backend/tests/infra/test_variflight_client.py`

**Interfaces:**
- Consumes: `AirportCatalog` and `ResolvedLocation` from Task 1.
- Produces: `build_flight_query(origin: str, destination: str, depart_date: str) -> FlightQuery`.
- Produces: `RouteRegion.mainland_domestic|cross_border|international`.

- [ ] **Step 1: Write failing location and route-classification tests**

```python
def test_build_query_supports_non_hot_mainland_city():
    query = build_flight_query("阿勒泰", "黔江", "2026-08-08")
    assert query.origin.city_name == "阿勒泰"
    assert query.destination.airport_iata == "JIQ"
    assert query.route_region is RouteRegion.mainland_domestic

def test_hong_kong_macau_taiwan_are_cross_border():
    assert build_flight_query("深圳", "香港", "2026-08-08").route_region is RouteRegion.cross_border
    assert build_flight_query("澳门", "台北", "2026-08-08").route_region is RouteRegion.cross_border

def test_unknown_city_is_validation_error():
    with pytest.raises(FlightQueryError, match="无法识别城市或机场"):
        build_flight_query("火星", "北京", "2026-08-08")
```

- [ ] **Step 2: Verify tests fail against hard-coded maps**

Run: `.venv/bin/pytest backend/tests/services/test_flight_query.py backend/tests/services/test_intent_slot_filler.py -v`

Expected: FAIL for unsupported cities and missing route classification.

- [ ] **Step 3: Implement query validation and route classification**

```python
class RouteRegion(str, Enum):
    mainland_domestic = "mainland_domestic"
    cross_border = "cross_border"
    international = "international"

@dataclass(frozen=True)
class FlightQuery:
    origin: ResolvedLocation
    destination: ResolvedLocation
    depart_date: date
    route_region: RouteRegion

def build_flight_query(origin: str, destination: str, depart_date: str) -> FlightQuery:
    catalog = AirportCatalog.load_default()
    origin_location = catalog.resolve_location(origin)
    destination_location = catalog.resolve_location(destination)
    if not origin_location or not destination_location:
        raise FlightQueryError("无法识别城市或机场")
    parsed_date = date.fromisoformat(depart_date)
    if parsed_date <= today_cn():
        raise FlightQueryError("出发日期必须是未来日期")
    return FlightQuery.from_locations(origin_location, destination_location, parsed_date)
```

Reject past/today dates before providers run. Use catalog aliases in deterministic slot parsing. Replace duplicate dictionaries with catalog calls; keep `HOT_ROUTES` as product configuration only, not validation.

- [ ] **Step 4: Run migration tests**

Run: `.venv/bin/pytest backend/tests/services/test_flight_query.py backend/tests/services/test_intent_slot_filler.py backend/tests/test_airport_mapping.py backend/tests/infra/test_variflight_client.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/flight_query.py backend/application/services/intent_slot_filler.py backend/services/intent_parser.py backend/third_party/flights_monitor/shared.py backend/infrastructure/flight_data/variflight_client.py backend/application/services/_routes.py backend/application/services/recommendation_service.py backend/tests
git commit -m "refactor(airports): use one location catalog"
```

---

### Task 3: Provider Contracts, FlyAI, and SerpAPI

**Files:**
- Create: `backend/application/contracts/flight_provider.py`
- Create: `backend/infrastructure/flight_data/providers/__init__.py`
- Create: `backend/infrastructure/flight_data/providers/flyai.py`
- Create: `backend/infrastructure/flight_data/providers/serpapi.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `frontend/.env.example`
- Test: `backend/tests/contracts/test_flight_provider_contracts.py`
- Test: `backend/tests/infra/test_flyai_provider.py`
- Test: `backend/tests/infra/test_serpapi_provider.py`
- Fixtures: `backend/tests/fixtures/providers/flyai_search.json`, `backend/tests/fixtures/providers/serpapi_search.json`, `backend/tests/fixtures/providers/serpapi_booking_options.json`

**Interfaces:**
- Consumes: `FlightQuery` from Task 2.
- Produces: `FlightProvider.search(query: FlightQuery) -> ProviderResult`.
- Produces price statuses `priced|view_live_price|stale` and provider statuses `loading|queued|success|empty|stale|timeout|disabled|error`.

- [ ] **Step 1: Write failing contract and fixture tests**

```python
def test_offer_allows_unknown_components_but_requires_price_or_url():
    offer = FlightOffer(
        data_provider="flyai", seller_name="飞猪", flight_no="CA123",
        depart_date=date(2026, 8, 8), base_price=580, tax=None,
        baggage_fee=None, total_price=None, display_price=580,
        price_status=PriceStatus.priced, booking_url="https://example.test/f",
    )
    assert offer.tax is None

@pytest.mark.asyncio
async def test_flyai_missing_price_keeps_https_jump_url(fake_cli, domestic_query):
    fake_cli.stdout = '{"items":[{"flightNo":"CA123","jumpUrl":"https://example.test/f"}]}'
    result = await FlyAIProvider(api_key="secret", runner=fake_cli).search(domestic_query)
    assert result.status is ProviderStatus.success
    assert result.offers[0].price_status is PriceStatus.view_live_price
    assert result.offers[0].booking_url == "https://example.test/f"

@pytest.mark.asyncio
async def test_serpapi_uses_actual_seller_name(mock_transport, cross_border_query):
    provider = SerpApiProvider(api_key="secret", client=httpx.AsyncClient(transport=mock_transport))
    result = await provider.search(cross_border_query)
    assert result.status is ProviderStatus.success
    assert result.offers[0].seller_name == "Trip.com"
    assert result.offers[0].data_provider == "serpapi_google_flights"
```

- [ ] **Step 2: Verify imports fail**

Run: `.venv/bin/pytest backend/tests/contracts/test_flight_provider_contracts.py backend/tests/infra/test_flyai_provider.py backend/tests/infra/test_serpapi_provider.py -v`

Expected: FAIL because provider contracts and adapters do not exist.

- [ ] **Step 3: Implement contracts and settings**

Add settings with empty defaults: `flyai_api_key`, `flyai_executable="flyai"`, `serpapi_api_key`, and `flight_provider_timeout_seconds=10.0`. Define `FlightOffer`, `ProviderResult`, and a runtime-checkable `FlightProvider` protocol. Validate booking URLs as HTTPS and require either a positive `display_price` or a valid booking URL.

- [ ] **Step 4: Implement safe FlyAI CLI adapter**

Use `asyncio.create_subprocess_exec` with an argument array, never `shell=True` and never request-time `npx`. Pass normalized Chinese full city names and a future date. Parse JSON stdout, redact stderr, return `disabled` without a key, do not retry `401`, and preserve `jumpUrl` when price is absent.

- [ ] **Step 5: Implement SerpAPI adapter**

Use an injected `httpx.AsyncClient`, `engine=google_flights`, `currency=CNY`, and provider airport codes. Call booking-options only when needed. Exclude `mainland_domestic`; include cross-border and international routes. Preserve response currency if not CNY and expose actual seller/airline names.

- [ ] **Step 6: Run provider tests**

Run: `.venv/bin/pytest backend/tests/contracts/test_flight_provider_contracts.py backend/tests/infra/test_flyai_provider.py backend/tests/infra/test_serpapi_provider.py -v`

Expected: PASS with no real third-party calls.

- [ ] **Step 7: Commit**

```bash
git add backend/application/contracts/flight_provider.py backend/infrastructure/flight_data/providers backend/config.py backend/requirements.txt frontend/.env.example backend/tests/contracts backend/tests/infra/test_flyai_provider.py backend/tests/infra/test_serpapi_provider.py backend/tests/fixtures/providers
git commit -m "feat(flights): add real-time provider adapters"
```

---

### Task 4: Pure Ctrip Parser and Explicit Error Model

**Files:**
- Create: `backend/infrastructure/flight_data/ctrip_parser.py`
- Create: `backend/application/contracts/collector.py`
- Modify: `backend/data_sources/ctrip_source.py`
- Modify: `backend/third_party/flights_monitor/ctrip_api.py`
- Create: `backend/requirements-collector.txt`
- Test: `backend/tests/infra/test_ctrip_parser.py`
- Modify: `backend/tests/test_ctrip_source.py`
- Fixture: `backend/tests/fixtures/providers/ctrip_batch_search.json`

**Interfaces:**
- Produces: `parse_batch_search(payload: Mapping[str, Any], query: FlightQuery) -> list[FlightOffer]`.
- Produces: `CollectorErrorCode.dependency_error|login_required|captcha_required|timeout|empty|parse_error`.
- Produces collector-only dependency manifest including `selenium>=4.22,<5.0`.

- [ ] **Step 1: Write failing truthfulness and dependency tests**

```python
def test_parser_keeps_only_real_ctrip_fields(ctrip_payload, query):
    offers = parse_batch_search(ctrip_payload, query)
    assert offers[0].seller_name == "携程"
    assert offers[0].display_price > 0
    assert offers[0].tax is None
    assert offers[0].baggage_fee is None
    assert {o.seller_name for o in offers} == {"携程"}

@pytest.mark.asyncio
async def test_missing_selenium_is_dependency_error(monkeypatch):
    result = await CtripSource(enable_mock_fallback=False).search_with_status(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )
    assert result.error_code == "dependency_error"
```

- [ ] **Step 2: Verify current code fails because it fabricates fields and swallows import errors**

Run: `.venv/bin/pytest backend/tests/infra/test_ctrip_parser.py backend/tests/test_ctrip_source.py -v`

Expected: FAIL on fake platform rows, fixed tax/baggage, and missing error status.

- [ ] **Step 3: Extract pure parser and status-bearing source API**

Implement `parse_batch_search` without Selenium imports. Add `CtripSource.search_with_status(origin: str, destination: str, date_start: str, date_end: str) -> CollectorSearchResult`; retain `search_flights` only as a compatibility wrapper returning `result.offers`. Convert import, Chrome startup, page state, timeout, empty response, and parse errors into explicit codes. Delete generated Qunar/FlyAI rows, `tax=120`, free-baggage defaults, inferred original prices, and fabricated verdicts.

- [ ] **Step 4: Separate Mac dependencies**

`backend/requirements-collector.txt` must include `-r requirements.txt` plus Selenium. Railway continues installing `backend/requirements.txt` only.

- [ ] **Step 5: Run parser/source tests**

Run: `.venv/bin/pytest backend/tests/infra/test_ctrip_parser.py backend/tests/test_ctrip_source.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/infrastructure/flight_data/ctrip_parser.py backend/application/contracts/collector.py backend/data_sources/ctrip_source.py backend/third_party/flights_monitor/ctrip_api.py backend/requirements-collector.txt backend/tests/infra/test_ctrip_parser.py backend/tests/test_ctrip_source.py backend/tests/fixtures/providers/ctrip_batch_search.json
git commit -m "fix(ctrip): expose real fields and explicit errors"
```

---

### Task 5: Collector Database Migration and Repositories

**Files:**
- Create: `backend/db/migrations/versions/20260718_ctrip_collector.py`
- Create: `backend/infrastructure/db/flight_demand_repo.py`
- Modify: `backend/infrastructure/db/flight_snapshot_repo.py`
- Test: `backend/tests/infra/test_flight_demand_repo.py`
- Modify: `backend/tests/infra/test_flight_snapshot_repo.py`
- Modify: `backend/tests/test_alembic_head.py`

**Interfaces:**
- Produces: `enqueue_demand(origin_code, destination_code, depart_date, source, priority) -> str` and `claim_next(node_id, lease_seconds) -> CollectorJob | None`.
- Produces: `complete_job(job_id, node_id, offers)`, `fail_job(job_id, node_id, error_code, retry_at)`, and `record_heartbeat(node_id, version, status)`.
- Produces: `upsert_provider_offers(provider, offers, ttl_minutes)` and `read_provider_deals(provider, origin_code, destination_code, depart_date)`.

- [ ] **Step 1: Write failing lease, priority, and stale-retention tests**

```python
async def test_claim_order_and_expired_lease(seeded_pg):
    low = await enqueue_demand("BJS", "SHA", "2026-08-08", "hot_route", 5)
    high = await enqueue_demand("BJS", "SYX", "2026-08-08", "price_alert", 100)
    claimed = await claim_next("mac-1", lease_seconds=60)
    assert claimed.job_id == high
    assert claimed.job_id != low

async def test_duplicate_hourly_demands_merge(seeded_pg):
    first = await enqueue_demand("BJS", "SHA", "2026-08-08", "recent_search", 50)
    second = await enqueue_demand("BJS", "SHA", "2026-08-08", "recent_search", 50)
    assert first == second

async def test_failed_job_preserves_last_successful_snapshot(seeded_pg, seeded_ctrip_snapshot):
    job = await claim_next("mac-1", lease_seconds=60)
    await fail_job(job.job_id, "mac-1", "timeout", retry_at=utcnow() + timedelta(minutes=5))
    rows = await read_provider_deals("ctrip_snapshot", "BJS", "SHA", "2026-08-08")
    assert rows
```

- [ ] **Step 2: Verify schema/repository tests fail**

Run: `.venv/bin/pytest backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py backend/tests/test_alembic_head.py -v`

Expected: FAIL for missing migration and repository functions.

- [ ] **Step 3: Add linear Alembic migration**

Create `flight_search_demands` with route/date, source, priority, status, attempts, next-attempt, lease owner/expiry, last error, and timestamps. Create `collector_nodes` with node ID, version, status, last heartbeat, and last success. Add `data_provider`, `currency`, `price_status`, and `expires_at` to platform snapshots plus provider-scoped indexes. Keep downgrade operations in exact reverse order.

- [ ] **Step 4: Implement transactional repositories**

Use PostgreSQL `FOR UPDATE SKIP LOCKED` for claims. Verify lease owner on complete/fail. Upsert child prices by `(flight_snapshot_id, data_provider, seller_name)` and never delete rows from another provider. Empty/failure updates the job only; successful offers update snapshots.

- [ ] **Step 5: Run repository and migration tests**

Run: `.venv/bin/pytest backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py backend/tests/test_alembic_head.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/db/migrations/versions/20260718_ctrip_collector.py backend/infrastructure/db/flight_demand_repo.py backend/infrastructure/db/flight_snapshot_repo.py backend/tests/infra/test_flight_demand_repo.py backend/tests/infra/test_flight_snapshot_repo.py backend/tests/test_alembic_head.py
git commit -m "feat(collector): add demand leases and provider snapshots"
```

---

### Task 6: Token-Authenticated Railway Collector API

**Files:**
- Create: `backend/schemas/collector.py`
- Create: `backend/api/collector.py`
- Modify: `backend/config.py`
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_collector_api.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: repositories from Task 5.
- Produces: `POST /internal/collector/claim`, `/heartbeat`, `/jobs/{job_id}/complete`, and `/jobs/{job_id}/fail`.

- [ ] **Step 1: Write failing auth and lifecycle API tests**

```python
async def test_collector_rejects_missing_or_wrong_token(client):
    assert (await client.post("/internal/collector/claim", json={"node_id": "mac-1"})).status_code == 401
    response = await client.post(
        "/internal/collector/claim",
        json={"node_id": "mac-1"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401

async def test_claim_returns_one_leased_job(client, collector_headers, seeded_demand):
    response = await client.post(
        "/internal/collector/claim", json={"node_id": "mac-1"}, headers=collector_headers
    )
    assert response.status_code == 200
    assert response.json()["job"]["job_id"] == seeded_demand.job_id

async def test_complete_validates_positive_price(client, collector_headers, seeded_lease):
    response = await client.post(
        f"/internal/collector/jobs/{seeded_lease.job_id}/complete",
        json={"node_id": "mac-1", "offers": [{"display_price": 0}]},
        headers=collector_headers,
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Verify endpoints are absent**

Run: `.venv/bin/pytest backend/tests/api/test_collector_api.py backend/tests/test_config.py -v`

Expected: FAIL with `404` and missing settings.

- [ ] **Step 3: Implement schemas, constant-time token auth, and endpoints**

Add empty-default settings `ctrip_collector_token`, `ctrip_snapshot_ttl_minutes=75`, `ctrip_collector_heartbeat_timeout_seconds=180`, and `ctrip_collector_lease_seconds=180`. Compare bearer tokens with `secrets.compare_digest`. Validate `data_provider == "ctrip_snapshot"`, job route/date match, CNY positive integer price, and allowlisted `https://flights.ctrip.com` booking URLs. Include the router without the public `/api` prefix.

- [ ] **Step 4: Add safe LangSmith spans**

Trace `ctrip_collector_claim` and `ctrip_collector_ingest` with anonymous job ID, result count, status, and duration only. Never attach token, cookie, profile path, account details, or raw payload.

- [ ] **Step 5: Run API tests**

Run: `.venv/bin/pytest backend/tests/api/test_collector_api.py backend/tests/test_config.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas/collector.py backend/api/collector.py backend/config.py backend/main.py backend/tests/api/test_collector_api.py backend/tests/test_config.py
git commit -m "feat(api): accept authenticated Ctrip collector results"
```

---

### Task 7: Mac Collector CLI, Persistent Chrome, and launchd

**Files:**
- Create: `backend/collector/__init__.py`
- Create: `backend/collector/client.py`
- Create: `backend/collector/browser.py`
- Create: `backend/collector/runner.py`
- Create: `backend/collector/cli.py`
- Create: `deploy/macos/com.faresniper.ctrip-collector.plist.template`
- Create: `scripts/install_macos_collector.sh`
- Create: `scripts/uninstall_macos_collector.sh`
- Test: `backend/tests/collector/test_client.py`
- Test: `backend/tests/collector/test_browser.py`
- Test: `backend/tests/collector/test_runner.py`

**Interfaces:**
- Consumes: internal API from Task 6 and parser from Task 4.
- Produces CLI: `python -m backend.collector.cli doctor|login|once|daemon`.
- Produces default profile `~/.faresniper/ctrip-profile` and config `~/.config/faresniper/collector.env`.

- [ ] **Step 1: Write failing client, browser-option, and runner tests**

```python
def test_browser_uses_dedicated_profile_and_no_proxy(tmp_path):
    options = build_chrome_options(profile_dir=tmp_path, headless=False)
    assert f"--user-data-dir={tmp_path}" in options.arguments
    assert "--no-proxy-server" in options.arguments

async def test_runner_reports_login_required_without_overwriting_snapshot(fake_api, fake_browser):
    fake_browser.result = CaptureResult(error_code="login_required")
    await CollectorRunner(fake_api, fake_browser).run_once()
    assert fake_api.fail_calls[0].error_code == "login_required"
    assert fake_api.complete_calls == []

async def test_runner_completes_with_normalized_real_offers(fake_api, fake_browser, ctrip_payload):
    fake_browser.result = CaptureResult(payloads=[ctrip_payload])
    await CollectorRunner(fake_api, fake_browser).run_once()
    assert fake_api.complete_calls[0].offers[0].seller_name == "携程"
    assert fake_api.complete_calls[0].offers[0].display_price > 0
```

- [ ] **Step 2: Verify collector modules are missing**

Run: `.venv/bin/pytest backend/tests/collector -v`

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement HTTP client and browser session**

Use `httpx.AsyncClient` with bearer token read from environment. Browser options must use the dedicated profile, `--no-proxy-server`, `NO_PROXY=127.0.0.1,localhost`, and visible mode for `login`. Never copy the default Chrome profile. Detect login/CAPTCHA pages by URL and stable page markers; return explicit statuses instead of bypass attempts.

- [ ] **Step 4: Implement one-job runner and daemon**

`once` sends heartbeat, claims one job, runs the Ctrip page capture, parses offers, and completes/fails exactly once. `daemon` repeats every 60 seconds and handles SIGINT/SIGTERM. Keep one browser task in flight. Emit `ctrip_local_collect` LangSmith traces without secrets.

- [ ] **Step 5: Implement installer and launch agent**

The installer must create `.venv-collector`, install `backend/requirements-collector.txt`, create a mode-`600` env file with empty token/API placeholders, render the plist with absolute repo/Python paths, run `doctor`, and instruct the user to execute `login` before loading the agent. Use `launchctl bootstrap gui/$UID` and `kickstart`; do not delete the profile on uninstall.

- [ ] **Step 6: Run collector tests and shell checks**

Run:

```bash
.venv/bin/pytest backend/tests/collector -v
bash -n scripts/install_macos_collector.sh scripts/uninstall_macos_collector.sh
plutil -lint deploy/macos/com.faresniper.ctrip-collector.plist.template
```

Expected: all tests PASS, shell syntax succeeds, plist is valid after substituting template variables in the test fixture.

- [ ] **Step 7: Commit**

```bash
git add backend/collector backend/tests/collector deploy/macos scripts/install_macos_collector.sh scripts/uninstall_macos_collector.sh
git commit -m "feat(collector): run Ctrip collection on macOS"
```

---

### Task 8: Ctrip Snapshot Provider and Concurrent Search Aggregator

**Files:**
- Create: `backend/infrastructure/flight_data/providers/ctrip_snapshot.py`
- Create: `backend/infrastructure/flight_data/providers/factory.py`
- Create: `backend/application/services/flight_search_aggregator.py`
- Modify: `backend/application/graph/tools/search_flights.py`
- Modify: `backend/api/search.py`
- Test: `backend/tests/infra/test_ctrip_snapshot_provider.py`
- Test: `backend/tests/services/test_flight_search_aggregator.py`
- Modify: `backend/tests/graph/tools/test_search_flights.py`
- Modify: `backend/tests/api/test_search.py`

**Interfaces:**
- Consumes: provider contracts, query builder, and repositories.
- Produces: `FlightSearchAggregator.search(query, emit=None) -> AggregatedSearchResult`.
- Produces: `POST /api/search/stream` NDJSON events `started|provider_status|results|validation_error|complete`.

- [ ] **Step 1: Write failing provider-isolation and progressive-result tests**

```python
async def test_ctrip_snapshot_returns_stale_offer_and_enqueues_refresh(stale_snapshot, domestic_query):
    result = await CtripSnapshotProvider().search(domestic_query)
    assert result.status is ProviderStatus.stale
    assert result.offers[0].display_price > 0
    assert await demand_exists(domestic_query)

async def test_one_provider_timeout_keeps_other_success(domestic_query):
    aggregator = FlightSearchAggregator([SlowProvider(), FakeProvider(price=580)], timeout_seconds=0.01)
    result = await aggregator.search(domestic_query)
    assert result.provider_statuses["slow"] is ProviderStatus.timeout
    assert result.offers[0].display_price == 580

async def test_mainland_excludes_serpapi(domestic_query):
    providers = build_flight_providers(settings_for_tests())
    assert "serpapi" not in [p.name for p in providers if p.supports(domestic_query)]
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/pytest backend/tests/infra/test_ctrip_snapshot_provider.py backend/tests/services/test_flight_search_aggregator.py backend/tests/graph/tools/test_search_flights.py backend/tests/api/test_search.py -v`

Expected: FAIL because provider factory, aggregator, and stream endpoint are missing.

- [ ] **Step 3: Implement snapshot provider and factory**

The snapshot provider reads valid or stale Ctrip rows, always enqueues refresh for missing/stale queries, and returns `queued|success|stale`. Factory order is FlyAI, Ctrip snapshot, SerpAPI; missing keys produce disabled providers, not startup failure.

- [ ] **Step 4: Implement concurrent aggregator**

Create one task per applicable provider and wrap each operation with `asyncio.wait_for(operation, timeout=10)`. Normalize and dedupe by flight number/date/time/airports, preserve multiple seller rows, and sort by available display price. Stale Ctrip prices may receive `lowest=True` but label the comparison as platform display price. Cancel unfinished tasks in `finally`.

- [ ] **Step 5: Replace mock fallback and add NDJSON stream**

Both JSON and stream endpoints use the same aggregator. Production never falls back to Mock when all configured real providers fail. Stream events carry `search_id` and monotonic `sequence`; the frontend may ignore older searches.

- [ ] **Step 6: Run search tests**

Run: `.venv/bin/pytest backend/tests/infra/test_ctrip_snapshot_provider.py backend/tests/services/test_flight_search_aggregator.py backend/tests/graph/tools/test_search_flights.py backend/tests/api/test_search.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/infrastructure/flight_data/providers backend/application/services/flight_search_aggregator.py backend/application/graph/tools/search_flights.py backend/api/search.py backend/tests/infra/test_ctrip_snapshot_provider.py backend/tests/services/test_flight_search_aggregator.py backend/tests/graph/tools/test_search_flights.py backend/tests/api/test_search.py
git commit -m "feat(search): aggregate progressive real fare providers"
```

---

### Task 9: Ground AI Text and Cards in One Final Deal Snapshot

**Files:**
- Create: `backend/application/services/grounded_response.py`
- Modify: `backend/application/graph/nodes/render_response.py`
- Modify: `backend/application/contracts/decision.py`
- Modify: `backend/tests/graph/nodes/test_render_response.py`
- Create: `backend/tests/services/test_grounded_response.py`

**Interfaces:**
- Produces: `build_response_facts(deals, budget, limit=7) -> ResponseFacts`.
- Produces: `render_flight_markdown(facts) -> str`.
- Produces: `validate_optional_prose(text, facts) -> str | None`.

- [ ] **Step 1: Write the exact ¥650-versus-¥700 regression test**

```python
@pytest.mark.asyncio
async def test_ai_price_cannot_disagree_with_card():
    state = {
        "search_result": {"deals": [deal("JD5121", 650), deal("JD5577", 700)]},
        "messages": [AIMessage(content="最低价是 ¥700，建议购买 JD5577")],
        "accumulated_slots": SlotBundle(budget=500),
        "request_user_id": "u1",
    }
    response = (await render_response(state))["response"]
    assert response.deals[0]["price"] == 650
    assert "¥650" in response.recommendation["text"]
    assert "最低价是 ¥700" not in response.recommendation["text"]
    assert "JD5121" in response.recommendation["text"]
```

- [ ] **Step 2: Verify current override reproduces the failure**

Run: `.venv/bin/pytest backend/tests/graph/nodes/test_render_response.py::test_ai_price_cannot_disagree_with_card -v`

Expected: FAIL because `_last_ai_text` overwrites the grounded recommendation.

- [ ] **Step 3: Implement immutable response facts and deterministic Markdown**

`ResponseFacts` contains the final ordered rows, best deal, minimum display price, budget, within-budget flag, and stale status. Generate the heading, table, recommendation, and alert suggestion from these facts. The first Markdown row must equal `deals[0]`; the minimum sentence must use the minimum eligible `display_price`.

- [ ] **Step 4: Stop free-form AI override for searches**

When `deals` exist, never replace `recommendation.text` with `_last_ai_text`. Optional LLM prose is accepted only when it contains no currency amount, flight number, or time token; otherwise discard it. When no deals exist, preserve current chitchat and slot-clarification behavior.

- [ ] **Step 5: Run response tests**

Run: `.venv/bin/pytest backend/tests/services/test_grounded_response.py backend/tests/graph/nodes/test_render_response.py backend/tests/graph/test_react_factory.py -v`

Expected: PASS, including the ¥650 regression and chitchat tests.

- [ ] **Step 6: Commit**

```bash
git add backend/application/services/grounded_response.py backend/application/graph/nodes/render_response.py backend/application/contracts/decision.py backend/tests/services/test_grounded_response.py backend/tests/graph/nodes/test_render_response.py
git commit -m "fix(response): ground fare text in final deals"
```

---

### Task 10: Nullable Fare Cards and Progressive Provider States

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/mappers.ts`
- Modify: `frontend/lib/useChatSession.ts`
- Modify: `frontend/components/chat-page.tsx`
- Modify: `frontend/components/discovery-card-content.tsx`
- Modify tests: `frontend/__tests__/api.test.ts`, `frontend/__tests__/mappers.test.ts`, `frontend/__tests__/chat-page.test.tsx`, `frontend/__tests__/component-chat-page.test.tsx`

**Interfaces:**
- Consumes: JSON/NDJSON search contracts from Tasks 8 and 9.
- Produces: `PriceItem` with nullable price, status, freshness, provider, and booking URL.

- [ ] **Step 1: Write failing UI state and consistency tests**

Add explicit fixtures and assertions for five cases: unknown tax/baggage renders `待确认` and never `¥0`; stale Ctrip renders its numeric price plus `价格可能已更新`; loading/queued/timeout/login-required each render their final copy; Markdown and card both contain the same best-deal price; an event with an older sequence or different active search ID does not replace current deals.

- [ ] **Step 2: Verify current numeric-only card types fail**

Run: `npm --prefix frontend test -- --run frontend/__tests__/mappers.test.ts frontend/__tests__/chat-page.test.tsx frontend/__tests__/component-chat-page.test.tsx`

Expected: FAIL because taxes, baggage, and platform prices are required numbers and no status UI exists.

- [ ] **Step 3: Expand DTOs and mappers**

Make `tax`, `baggage_fee`, and `PriceItem.price` nullable. Add `price_status`, `provider_status`, `data_provider`, `fetched_at`, `is_realtime`, and per-platform booking URL. Preserve `0` only when the provider explicitly confirms zero.

- [ ] **Step 4: Render truthful price components and statuses**

Display `待确认` for unknown tax/baggage, `查看实时价` only with a valid URL, stale numeric Ctrip prices with the warning, and explicit provider status copy. Replace “全网综合最优解/实时底价” with “平台展示价最低” whenever components are incomplete or any winning price is stale.

- [ ] **Step 5: Consume NDJSON progressively**

Add an `AbortController` per search. Replace deals with each full `results` snapshot, accept only increasing sequence values for the active `search_id`, and end all loading states on `complete` or network failure. Keep JSON fallback for compatibility.

- [ ] **Step 6: Run frontend tests and production build**

Run:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Expected: all Vitest tests PASS and Next.js build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib frontend/components frontend/__tests__
git commit -m "feat(ui): show truthful progressive fare states"
```

---

### Task 11: Deployment, Documentation, and End-to-End Verification

**Files:**
- Modify: `railway.toml`
- Modify: `backend/nixpacks.toml`
- Modify: `README.md`
- Modify: `docs/deployment/RAILWAY.md`
- Create: `docs/deployment/MAC_CTRIP_COLLECTOR.md`
- Create: `backend/scripts/verify_live_fares.py`
- Modify: `backend/tests/test_dependency_manifest.py`
- Modify: `backend/tests/test_e2e.py`

**Interfaces:**
- Consumes all prior tasks.
- Produces documented Railway variables, Mac setup, health checks, and an explicit live verification command.

- [ ] **Step 1: Write failing deployment-boundary and E2E tests**

Add manifest assertions that `backend/requirements.txt` excludes Selenium, `backend/requirements-collector.txt` includes `selenium>=4.22,<5.0`, and no `railway.toml` start command references collector/Chrome modules. Add an async E2E fixture that resolves `阿勒泰→三亚`, stores a Ctrip provider snapshot, calls search rendering, and asserts the same price in `deals[0]` and recommendation text.

- [ ] **Step 2: Verify tests expose old Railway Chrome assumptions**

Run: `.venv/bin/pytest backend/tests/test_dependency_manifest.py backend/tests/test_e2e.py -v`

Expected: FAIL until manifests and end-to-end flow are updated.

- [ ] **Step 3: Update Railway and environment documentation**

Railway backend receives `FLYAI_API_KEY`, `SERPAPI_API_KEY`, `CTRIP_COLLECTOR_TOKEN`, database, model, and LangSmith variables. Railway worker receives database/model/LangSmith variables but no Ctrip browser credentials. Remove Chromium/ChromeDriver from Railway build requirements when no remaining Railway code needs them. Document empty examples only.

- [ ] **Step 4: Document Mac installation and recovery**

Document prerequisites, `doctor`, first visible `login`, Clash direct behavior, agent install/status/log commands, token rotation, CAPTCHA/login recovery, sleep/uptime implications, and uninstall behavior. State explicitly that the profile stays local and that collection may be interrupted by Ctrip controls.

- [ ] **Step 5: Add explicit live verifier**

`verify_live_fares.py` accepts future route/date arguments, checks collector heartbeat, waits for a claimed/completed job with a bounded timeout, fetches the search response, asserts a Ctrip numeric price and booking URL, and prints related LangSmith trace names. It exits nonzero on stale-only results when `--require-fresh` is supplied.

- [ ] **Step 6: Run the full verification suite**

Run:

```bash
.venv/bin/pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
git diff --check
```

Expected: all tests PASS, frontend builds, and no whitespace errors.

- [ ] **Step 7: Run opt-in live checks**

Run after Railway variables and Mac token are configured:

```bash
.venv-collector/bin/python -m backend.collector.cli doctor
.venv-collector/bin/python -m backend.collector.cli once
.venv/bin/python -c 'from datetime import date,timedelta; print(date.today()+timedelta(days=7))' > /tmp/faresniper-future-date
.venv/bin/python -m backend.scripts.verify_live_fares \
  --origin 北京 --destination 三亚 --depart-date "$(cat /tmp/faresniper-future-date)" --require-fresh
```

Expected: collector health is online, at least one real Ctrip offer reaches Railway, FareSniper returns the same minimum price in text and card, and LangSmith contains collector/provider spans.

- [ ] **Step 8: Commit**

```bash
git add railway.toml backend/nixpacks.toml README.md docs/deployment backend/scripts/verify_live_fares.py backend/tests/test_dependency_manifest.py backend/tests/test_e2e.py
git commit -m "docs(deploy): ship Mac Ctrip collector workflow"
```

---

## Final Review Gate

- [ ] Run `git status --short` and confirm only intended files changed.
- [ ] Confirm `tmp/fill_explore_pool.py` and all user-owned unrelated files remain untouched and uncommitted.
- [ ] Run the complete backend and frontend test/build commands from Task 11.
- [ ] Review every provider log and LangSmith attribute for secrets, cookies, full third-party payloads, and PII.
- [ ] Compare one visible Ctrip page result with the uploaded snapshot and FareSniper card.
- [ ] Confirm AI Markdown first-row price, minimum-price sentence, alert suggestion, and card all equal the same final deal values.
- [ ] Request code review before merging or deploying.
