# Flight Price Display Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse FlyAI's production `ticketPrice` and allow the latest expired Ctrip snapshot to display, win the price comparison, and drive the Ctrip booking link.

**Architecture:** Keep provider freshness truthful while separating winner eligibility from real-time marketing. FlyAI normalizes the current and legacy price fields at the provider boundary; the backend winner contract narrowly permits stale `ctrip_snapshot` rows with numeric prices and HTTPS links; the frontend accepts that contract, renders numeric stale rows, and reserves real-time copy for genuinely fresh inventory.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, FastAPI wire DTOs, TypeScript, React 19, Vitest, Testing Library.

## Global Constraints

- Prefer FlyAI `ticketPrice`; use `adultPrice` only as a compatibility fallback.
- A stale Ctrip numeric snapshot participates in same-currency minimum-price comparison.
- A winning stale Ctrip row drives the headline amount, `winning_price_id`, "最低" badge, and Ctrip HTTPS booking link.
- Keep stale Ctrip metadata stale; never describe it as a real-time price.
- Display the stale Ctrip amount without "上次采集" or "价格可能已更新" replacing the number.
- Do not make stale SerpAPI, FlyAI, legacy, or unknown-provider rows eligible winners.
- Do not invent tax, fuel surcharge, baggage fee, or zero prices.
- Keep the hourly Ctrip refresh and stale-demand enqueue behavior unchanged.

## File Map

- `backend/infrastructure/flight_data/providers/flyai.py`: normalize current and legacy FlyAI price fields.
- `backend/tests/fixtures/providers/flyai_search_success.json`: mirror the current production FlyAI payload shape.
- `backend/tests/infra/test_flyai_provider.py`: provider-boundary price regression tests.
- `backend/application/services/flight_offer_normalizer.py`: select narrowly eligible stale Ctrip winners.
- `backend/schemas/common.py`: validate fresh winners and stale Ctrip winners without conflating them.
- `backend/tests/services/test_flight_offer_normalizer.py`: winner-selection regression tests.
- `backend/tests/test_schemas.py`: backend DTO contract regression tests.
- `frontend/lib/api.ts`: validate the same two winner states on the wire.
- `frontend/components/discovery-card-content.tsx`: separate selected-winner UI from real-time-winner UI and keep numeric stale prices visible.
- `frontend/__tests__/api.test.ts`: wire validation regression tests.
- `frontend/__tests__/discovery-card-content.test.tsx`: stale Ctrip amount, badge, copy, and link regression tests.

---

### Task 1: Parse Current FlyAI Ticket Prices

**Files:**
- Modify: `backend/tests/fixtures/providers/flyai_search_success.json`
- Modify: `backend/tests/infra/test_flyai_provider.py`
- Modify: `backend/infrastructure/flight_data/providers/flyai.py`

**Interfaces:**
- Consumes: FlyAI item dictionaries containing `ticketPrice`, optional legacy `adultPrice`, `journeys`, and `jumpUrl`.
- Produces: `parse_flyai_payload(payload: dict, query: FlightQuery) -> list[FlightOffer]` with `total_price: int | None`.

- [ ] **Step 1: Replace the fixture price field with the production shape**

Change the fixture's first offer from:

```json
"adultPrice": "¥400.0"
```

to:

```json
"ticketPrice": "400.00"
```

- [ ] **Step 2: Add current-field, usable-fallback, and precedence tests**

Add tests that prove the fixture parses to `400`, that an item with an unusable `ticketPrice` and `adultPrice="¥410.0"` parses to `410`, and that valid `ticketPrice` values, including `"0"`, take precedence over `adultPrice`:

```python
def test_parser_falls_back_to_adult_price_when_ticket_price_is_unusable():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["ticketPrice"] = "not available"
    item["adultPrice"] = "¥410.0"

    assert parse_flyai_payload(payload, _query())[0].total_price == 410


def test_parser_keeps_zero_ticket_price_ahead_of_adult_price():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["ticketPrice"] = "0"
    item["adultPrice"] = "999.00"

    assert parse_flyai_payload(payload, _query())[0].total_price == 0
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://localhost/faresniper_test \
pytest -q backend/tests/infra/test_flyai_provider.py
```

Expected: the unusable-`ticketPrice` fallback test fails because `adultPrice` is not parsed after an unusable current value; valid-zero precedence may already pass.

- [ ] **Step 4: Implement explicit parsed-value fallback**

Parse `ticketPrice` first and parse `adultPrice` only when the first parse returns `None`, so an unusable current value falls back while numeric zero remains authoritative:

```python
price = _parse_price(item.get("ticketPrice"))
if price is None:
    price = _parse_price(item.get("adultPrice"))
```

- [ ] **Step 5: Run the provider tests and verify GREEN**

Run the Step 3 command.

Expected: all FlyAI provider tests pass.

- [ ] **Step 6: Commit the provider fix**

```bash
git add backend/infrastructure/flight_data/providers/flyai.py \
  backend/tests/fixtures/providers/flyai_search_success.json \
  backend/tests/infra/test_flyai_provider.py
git commit -m "fix(flights): parse FlyAI ticket prices"
```

---

### Task 2: Select Expired Ctrip Prices Without Claiming Freshness

**Files:**
- Modify: `backend/tests/services/test_flight_offer_normalizer.py`
- Modify: `backend/tests/test_schemas.py`
- Modify: `backend/application/services/flight_offer_normalizer.py`
- Modify: `backend/schemas/common.py`

**Interfaces:**
- Consumes: `FlightOffer` rows and `ProviderResult` statuses from FlyAI and Ctrip snapshot providers.
- Produces: one `DealCardDto` winner that is either a fresh real-time priced offer or a numeric stale `ctrip_snapshot` offer with an HTTPS booking URL.

- [ ] **Step 1: Add a stale-Ctrip-wins normalizer test**

Construct one live FlyAI `560 CNY` offer and one stale non-real-time Ctrip `500 CNY` offer for the same flight identity:

```python
def test_stale_ctrip_snapshot_can_win_and_drive_headline_and_booking():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪", price=560)],
        ),
        "ctrip": ProviderResult(
            provider="ctrip",
            status=ProviderStatus.stale,
            offers=[
                _offer(
                    provider="ctrip_snapshot",
                    seller="携程",
                    price=500,
                    status=PriceStatus.stale,
                    realtime=False,
                    booking_url="https://ctrip.example.test/book",
                    expires_at="2000-01-01T00:00:00+00:00",
                )
            ],
        ),
    }

    deal = offers_to_deals(_query(), results)[0]

    assert deal["platform"] == "携程"
    assert deal["total_price"] == 500
    assert deal["booking_url"] == "https://ctrip.example.test/book"
    assert deal["data_freshness"] == "stale"
    winner = next(row for row in deal["prices"] if row["lowest"])
    assert winner["data_provider"] == "ctrip_snapshot"
    assert winner["price_status"] == "stale"
```

Add a sibling test proving a cheaper stale SerpAPI row cannot beat a live FlyAI offer.

- [ ] **Step 2: Add backend DTO acceptance and rejection tests**

Add a valid stale Ctrip winner payload:

```python
def test_deal_card_accepts_stale_ctrip_winner_with_matching_link():
    row = {
        **_deal_payload()["prices"][0],
        "id": "ctrip-stale-cny",
        "name": "携程",
        "price": 500,
        "lowest": True,
        "price_status": "stale",
        "provider_status": "stale",
        "url": "https://ctrip.example.test/book",
        "data_provider": "ctrip_snapshot",
        "data_freshness": "stale",
        "expires_at": "2000-01-01T00:00:00+00:00",
    }
    dto = DealCardDto.model_validate(
        _deal_payload(
            platform="携程",
            price=500,
            lowest_price=500,
            total_price=500,
            winning_price_id="ctrip-stale-cny",
            data_freshness="stale",
            prices=[row],
            booking_url="https://ctrip.example.test/book",
            h5_fallback_url="https://ctrip.example.test/book",
            inventory_expires_at="2000-01-01T00:00:00+00:00",
        )
    )
    assert dto.winning_price_id == "ctrip-stale-cny"
```

Add parameterized rejection cases changing `data_provider` away from `ctrip_snapshot`, removing the HTTPS URL, or changing `provider_status` away from `stale`.

- [ ] **Step 3: Run the focused backend tests and verify RED**

Run:

```bash
DATABASE_URL=postgresql+asyncpg://localhost/faresniper_test \
pytest -q backend/tests/services/test_flight_offer_normalizer.py \
  backend/tests/test_schemas.py
```

Expected: stale Ctrip is not selected and the DTO rejects the stale winner.

- [ ] **Step 4: Narrowly extend backend winner eligibility**

Introduce focused predicates in `flight_offer_normalizer.py`:

```python
def _is_stale_ctrip_candidate(
    offer: FlightOffer, provider_status: ProviderStatus, *, now: datetime
) -> bool:
    return (
        offer.data_provider == "ctrip_snapshot"
        and provider_status is ProviderStatus.stale
        and offer.price_status is PriceStatus.stale
        and isinstance(offer.total_price, int)
        and offer.booking_url is not None
        and _offer_freshness(offer, provider_status, now=now) == "stale"
    )


def _is_ranked_offer(
    offer: FlightOffer, provider_status: ProviderStatus, *, now: datetime
) -> bool:
    is_fresh_realtime = (
        offer.is_realtime
        and _is_fresh_numeric(offer)
        and _offer_freshness(offer, provider_status, now=now) == "fresh"
    )
    return is_fresh_realtime or _is_stale_ctrip_candidate(
        offer, provider_status, now=now
    )
```

Keep currency selection and numeric ordering unchanged so the lower eligible amount wins.

- [ ] **Step 5: Extend the Pydantic winner contract with two explicit states**

In `DealCardDto.validate_winning_price_contract`, accept either:

```python
fresh_winner = (
    winner.price_status is PriceStatus.priced
    and winner.provider_status is ProviderStatus.success
    and winner.data_freshness == "fresh"
)
stale_ctrip_winner = (
    winner.data_provider == "ctrip_snapshot"
    and winner.price_status is PriceStatus.stale
    and winner.provider_status is ProviderStatus.stale
    and winner.data_freshness == "stale"
    and winner.url is not None
)
```

Require one of these states while retaining all existing headline, amount, currency, row ID, expiry, and booking URL equality checks.

- [ ] **Step 6: Run the focused backend tests and verify GREEN**

Run the Step 3 command.

Expected: all normalizer and schema tests pass.

- [ ] **Step 7: Commit the backend winner contract**

```bash
git add backend/application/services/flight_offer_normalizer.py \
  backend/schemas/common.py \
  backend/tests/services/test_flight_offer_normalizer.py \
  backend/tests/test_schemas.py
git commit -m "fix(flights): let Ctrip snapshots win comparisons"
```

---

### Task 3: Render Numeric Stale Ctrip Winners

**Files:**
- Modify: `frontend/__tests__/api.test.ts`
- Modify: `frontend/__tests__/discovery-card-content.test.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/discovery-card-content.tsx`

**Interfaces:**
- Consumes: backend `DealCardDto` with either a fresh winner or a stale `ctrip_snapshot` winner.
- Produces: validated `DealCardDto` values and a card where any known numeric row remains visible, the selected winner receives "最低", and only a fresh winner receives real-time copy.

- [ ] **Step 1: Add a wire-validation regression test**

Use `validDeal` with a stale Ctrip winner and assert the stream result is accepted rather than discarded:

```typescript
const staleCtrip = validPriceItem({
  id: "ctrip-stale-cny",
  name: "携程",
  price: 500,
  lowest: true,
  price_status: "stale",
  provider_status: "stale",
  data_provider: "ctrip_snapshot",
  data_freshness: "stale",
  url: "https://ctrip.example.test/book",
  expires_at: "2000-01-01T00:00:00+00:00",
});
const deal = validDeal({
  platform: "携程",
  price: 500,
  lowest_price: 500,
  total_price: 500,
  winning_price_id: "ctrip-stale-cny",
  prices: [staleCtrip],
  booking_url: "https://ctrip.example.test/book",
  h5_fallback_url: "https://ctrip.example.test/book",
  data_freshness: "stale",
  inventory_expires_at: "2000-01-01T00:00:00+00:00",
});
```

Add one rejection assertion for the same stale winner with `data_provider: "serpapi_google_flights"`.

- [ ] **Step 2: Add the card rendering regression test**

Render a stale Ctrip winner at `500 CNY` and a live FlyAI nonwinner at `560 CNY`. Assert:

```typescript
expect(screen.getByText("¥500")).toBeInTheDocument();
expect(screen.getByText("¥560")).toBeInTheDocument();
expect(within(screen.getByText("携程").parentElement!).getByText("最低")).toBeInTheDocument();
expect(screen.getByRole("link", { name: "前往预订" })).toHaveAttribute(
  "href",
  "https://ctrip.example.test/book",
);
expect(screen.queryByText("价格可能已更新")).not.toBeInTheDocument();
expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
```

- [ ] **Step 3: Run focused frontend tests and verify RED**

Run:

```bash
cd frontend
npm test -- --run __tests__/api.test.ts __tests__/discovery-card-content.test.tsx
```

Expected: wire validation rejects the stale winner; the card hides the stale amount, badge, or booking link.

- [ ] **Step 4: Accept the narrow stale Ctrip state in `frontend/lib/api.ts`**

Keep existing shared winner/headline equality checks and replace the single fresh-state requirement with:

```typescript
const freshWinner =
  winner.price_status === "priced" &&
  winner.provider_status === "success" &&
  winner.data_freshness === "fresh";
const staleCtripWinner =
  winner.data_provider === "ctrip_snapshot" &&
  winner.price_status === "stale" &&
  winner.provider_status === "stale" &&
  winner.data_freshness === "stale" &&
  isCompleteHttpsUrl(winner.url);
```

Require `freshWinner || staleCtripWinner`.

- [ ] **Step 5: Separate selected winner from real-time winner in the card**

Create a selected-winner predicate that checks ID, amount, currency, platform, headline freshness, and one of the two accepted states. A fresh selected winner requires both current inventory expiry and current winning-row expiry; only the explicit stale Ctrip snapshot winner is exempt from those expiry checks. Derive:

```typescript
const freshWinner =
  price.provider_status === "success" &&
  price.price_status === "priced" &&
  price.data_freshness === "fresh" &&
  isExpiryCurrent(inventoryExpiresAt, expiryNow) &&
  isExpiryCurrent(price.expires_at, expiryNow);
const staleCtripWinner =
  price.data_provider === "ctrip_snapshot" &&
  price.provider_status === "stale" &&
  price.price_status === "stale" &&
  price.data_freshness === "stale" &&
  isHttpsUrl(price.url);
const selectedWinner = prices.find(isSelectedWinner);
const hasSelectedWinner = selectedWinner !== undefined;
const hasRealtimeWinner =
  selectedWinner !== undefined &&
  selectedWinner.provider_status === "success" &&
  selectedWinner.price_status === "priced" &&
  selectedWinner.data_freshness === "fresh" &&
  dataFreshness === "fresh" &&
  isExpiryCurrent(inventoryExpiresAt, expiryNow) &&
  isExpiryCurrent(selectedWinner.expires_at, expiryNow);
```

Use `hasSelectedWinner` for the "最低" badge and safe HTTPS booking action only after the fresh selected-winner expiry requirements above are met, or for the explicit stale Ctrip snapshot exception. Continue using `hasRealtimeWinner` for "实时底价", "全网多端实时同步", pulsing decoration, and real-time recommendation copy.

- [ ] **Step 6: Render numeric rows before provider status copy**

Change the row value selection to:

```typescript
const displayedValue =
  price.price !== null
    ? rowPrice
    : providerMessage ?? rowPrice;
```

Keep `view_live_price` as a link only for an unpriced successful fresh row with a valid HTTPS URL. Render `displayedValue` for every other row.

- [ ] **Step 7: Run focused frontend tests and verify GREEN**

Run the Step 3 command.

Expected: both test files pass.

- [ ] **Step 8: Commit the frontend contract and rendering fix**

```bash
git add frontend/lib/api.ts \
  frontend/components/discovery-card-content.tsx \
  frontend/__tests__/api.test.ts \
  frontend/__tests__/discovery-card-content.test.tsx
git commit -m "fix(ui): display winning Ctrip snapshot prices"
```

---

### Task 4: Cross-Layer Verification and Deployment Readiness

**Files:**
- Verify only; modify a fixture or contract test only if a cross-layer mismatch is discovered through a new failing regression.

**Interfaces:**
- Consumes: the completed provider, backend winner, wire validation, and card rendering changes.
- Produces: a reviewed branch that is ready to merge and deploy.

- [ ] **Step 1: Run all affected backend unit and contract tests**

```bash
DATABASE_URL=postgresql+asyncpg://localhost/faresniper_test \
pytest -q \
  backend/tests/infra/test_flyai_provider.py \
  backend/tests/services/test_flight_offer_normalizer.py \
  backend/tests/test_schemas.py \
  backend/tests/contracts/test_flight_wire_contract.py \
  backend/tests/api/test_search_stream.py
```

Expected: all tests pass without connecting to production. Tests requiring the dedicated PostgreSQL fixture must be run only when `TEST_DATABASE_URL` points to a non-production database.

- [ ] **Step 2: Run frontend tests, type checking, and production build**

```bash
cd frontend
npm test -- --run __tests__/api.test.ts \
  __tests__/discovery-card-content.test.tsx \
  __tests__/backend-wire-contract.test.ts
npm run lint
npm run build
```

Expected: tests, TypeScript checking, and Next.js production build pass.

- [ ] **Step 3: Run static checks**

```bash
python3 -m py_compile \
  backend/infrastructure/flight_data/providers/flyai.py \
  backend/application/services/flight_offer_normalizer.py \
  backend/schemas/common.py
git diff --check main...HEAD
```

Expected: no syntax or whitespace errors.

- [ ] **Step 4: Request two-stage review**

Use a fresh specification reviewer to compare the implementation to `docs/superpowers/specs/2026-07-18-flight-price-display-correction-design.md`, then a fresh code-quality reviewer. Resolve every Critical or Important finding with a new failing regression before implementation changes.

- [ ] **Step 5: Perform a safe production smoke after deployment**

After merge and Railway deployment, query a future Beijing-to-Shanghai date. Verify the response contains numeric FlyAI prices parsed from `ticketPrice`. If a Ctrip snapshot exists for a matching flight, verify the row remains numeric when stale and can become `winning_price_id` when lower. Confirm the winning HTTPS URL belongs to the selected provider and LangSmith records `provider.flyai` and `provider.ctrip` child spans without raw offers or URLs.

- [ ] **Step 6: Commit review-only corrections if any**

```bash
git add backend/infrastructure/flight_data/providers/flyai.py \
  backend/application/services/flight_offer_normalizer.py \
  backend/schemas/common.py \
  backend/tests/infra/test_flyai_provider.py \
  backend/tests/services/test_flight_offer_normalizer.py \
  backend/tests/test_schemas.py \
  frontend/lib/api.ts \
  frontend/components/discovery-card-content.tsx \
  frontend/__tests__/api.test.ts \
  frontend/__tests__/discovery-card-content.test.tsx
git commit -m "test(flights): close price display review gaps"
```

Skip this commit when review produces no changes.
