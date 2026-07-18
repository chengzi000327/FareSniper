# Final Review Fix Report

Date: 2026-07-18
Branch: `codex/multi-provider-flight-search`
Review base: `7ef5946298d1bf98d5f984ea5d5f6dab36cff514`
Fix starting point: `64a913fbac1635e8222c16d195852913f3061f5a`
Commit: enclosing commit with message `fix(flights): close final review gaps`; the final object hash is reported by `git rev-parse HEAD` after commit because a commit cannot contain its own hash.

## Outcome

All Critical and Important findings C1 and I1-I7 were fixed in one TDD wave. The duplicate provider/seller/currency row Minor was also resolved. Public responses retain only complete HTTPS booking deep links, while model/tool and tracing summaries remain URL-free and secret-free. No paid or live provider calls were made.

## Root Causes

### C1: wire schema drift

The backend reused `status` for price state while the frontend interpreted it as provider state. Progressive rows omitted a score that the frontend required, and the UI substituted `9.5`. There was no backend-generated contract artifact exercising the frontend runtime parser.

### I1: one sanitizer served incompatible audiences

The public stream sanitizer removed query strings and fragments from all URLs, breaking booking deep links. The tool router then serialized the unsanitized result with `str(result)`, exposing those same links to the model. Secret-key filtering also depended on suffix-only matching.

### I2: subprocess ownership ended at the parent PID

FlyAI inherited the complete service environment. Timeout cleanup killed only the immediate process, and outer cancellation or a nonzero/invalid-output error could leave descendants alive.

### I3: persistence inferred replacement scope from returned rows

An empty successful scrape had no rows from which to infer route/date scope, so it was skipped. Partial refreshes deleted only rows for returned flights, leaving sold-out provider rows visible.

### I4: Selenium ran in an unkillable thread

The Ctrip collection path used `asyncio.to_thread`; cancellation could not stop the browser thread or Chrome tree. Navigation also lacked a page-load timeout.

### I5: currency was treated as presentation metadata

SerpAPI response currency was dropped, the normalizer and recommendation path could choose numeric minima across currencies, repository readers ordered mixed currencies by raw amount, and frontend mappers/cards hardcoded CNY display.

### I6: historical fallback crossed the booking boundary

The recommendation pool fell back to the newest stored batch without a future-date condition, then generated a booking URL for that historical departure.

### I7: pagination preceded renderability

The backend sliced the raw card pool before removing cards without previews. The frontend stopped on an empty page, so later valid cards could be stranded.

### Minor: duplicate rows were not stable

Provider/seller/currency duplicates could produce repeated React keys. Equal-price deduplication also preferred the oldest timestamp lexically.

## RED Evidence

Every behavior change was preceded by a focused failing regression. The initial wave produced these expected failures before production edits:

| Finding | Focused command | Observed RED |
| --- | --- | --- |
| C1 | `pytest -q backend/tests/contracts/test_flight_wire_contract.py` | Collection error because the backend fixture generator did not exist. |
| C1 | `npm --prefix frontend run test -- --run __tests__/backend-wire-contract.test.ts` | 1 failed: the real progressive payload was rejected as `invalid stream event`. |
| C1/I5/Minor | `pytest -q backend/tests/services/test_flight_offer_normalizer.py` with the new wire, mixed-currency, and duplicate node IDs | 3 new regressions failed: missing split statuses/currency/nullable score, USD 80 beat CNY 550, and duplicate rows remained. |
| I1 | `pytest -q backend/tests/services/test_flight_search_aggregator.py::test_public_event_preserves_complete_https_booking_deep_link backend/tests/graph/nodes/test_tool_router.py::test_search_tool_message_is_url_free_while_state_keeps_public_links` | 2 failed: the public query was stripped and the model message retained the URL. |
| I2 | `pytest -q backend/tests/infra/test_flyai_provider.py::test_child_environment_is_a_minimal_allowlist backend/tests/infra/test_flyai_provider.py::test_outer_cancellation_kills_process_group_and_awaits_cleanup` | 2 failed: inherited secrets/start-session mismatch and no group cleanup on cancellation. |
| I3 | `pytest -q backend/tests/workers/test_ctrip_refresh.py::test_successful_empty_refresh_replaces_the_route_inventory backend/tests/infra/test_flight_snapshot_repo.py::test_provider_refresh_atomically_replaces_partial_route_inventory backend/tests/infra/test_flight_snapshot_repo.py::test_provider_refresh_with_empty_success_clears_route_inventory` | 3 failed: empty success skipped persistence and repository replacement lacked explicit scope. |
| I4 | `pytest -q backend/tests/test_ctrip_source.py::test_hanging_navigation_kills_browser_process_group_without_live_browser backend/tests/test_ctrip_source.py::test_ctrip_client_sets_a_page_load_timeout` | 2 failed: no supervised process group and no Selenium page-load timeout. |
| I5 | `pytest -q backend/tests/infra/test_serpapi_provider.py::test_retains_response_currency_instead_of_assuming_query_currency backend/tests/graph/nodes/test_render_response.py::test_final_analysis_does_not_compare_unlike_currencies` | 2 failed: SerpAPI became CNY and response analysis compared unlike currencies. |
| I5 frontend | `npm --prefix frontend run test -- --run __tests__/mappers.test.ts __tests__/discovery-card-content.test.tsx __tests__/component-chat-page.test.tsx` | New mapper/card/chat assertions failed because currency was dropped, CNY was hardcoded, and `9.5` was fabricated. |
| I6/I7 | `pytest -q backend/tests/services/test_recommendation_final_review.py` | 3 failed initially: empty cards were sliced first, historical inventory remained eligible, and preview currency/unknown values were fabricated or dropped. |
| I6 | `pytest -q backend/tests/infra/test_flight_snapshot_repo.py::test_read_deals_latest_excludes_historical_departures` | Failed because `today`/future filtering was absent. |
| I7 frontend | `npm --prefix frontend run test -- --run __tests__/explore-page.test.tsx -t "continues past an empty first page"` | 1 failed because only offset 0 was requested. |

Self-review then added and observed these additional RED cases before their fixes:

```text
pytest -q \
  backend/tests/infra/test_flyai_provider.py::test_nonzero_exit_kills_process_group_and_awaits_cleanup \
  backend/tests/test_ctrip_source.py::test_malformed_worker_payload_kills_process_group_and_awaits_cleanup \
  backend/tests/infra/test_ctrip_snapshot_provider.py::test_snapshot_price_selection_prefers_query_currency_before_amount \
  backend/tests/services/test_recommendation_final_review.py::test_card_pool_selects_and_compares_one_currency_per_route \
  backend/tests/graph/nodes/test_tool_router.py::test_search_tool_message_is_url_free_while_state_keeps_public_links
```

Result: `5 failed`. Error cleanup did not kill exited-parent process groups, both selection paths chose USD 80 over CNY 550, and embedded secret fields survived.

```text
pytest -q backend/tests/infra/test_flight_snapshot_repo.py::test_deal_sort_key_groups_currency_before_numeric_amount
```

Result: collection error because `_deal_sort_key` did not exist.

```text
npm --prefix frontend run test -- --run __tests__/api.test.ts -t "stream accepts backend-valid null lowest state"
```

Result: `1 failed`; `lowest: null` was rejected.

```text
pytest -q backend/tests/services/test_flight_offer_normalizer.py::test_duplicate_equal_prices_keep_the_freshest_offer
```

Result: `1 failed`; the older link won.

```text
pytest -q backend/tests/graph/nodes/test_tool_router.py::test_search_tool_message_is_url_free_while_state_keeps_public_links
```

Result: `1 failed`; secret markers embedded inside longer keys survived.

```text
pytest -q backend/tests/test_ctrip_source.py::test_ctrip_source_defaults_to_no_mock_fallback
```

Result: `1 failed`; the constructor default was still `True`.

## Implementation By Finding

### C1: explicit backend-to-frontend wire contract

- Added explicit `PriceItemDto` fields for row identity, currency, price status, provider status, URL, and provider source.
- Made `DealCardDto.recommend_score` nullable and made flight identity, duration, stops, total/lowest values, and currency explicit.
- Serialized every progressive deal through `DealCardDto` before emission.
- Split frontend `ProviderStatus` from `PriceStatus`, including runtime validation for `priced`.
- Aligned nullable fields and complete-HTTPS URL validation in the TypeScript parser.
- Added `backend/scripts/generate_flight_wire_fixture.py` and committed `frontend/__tests__/fixtures/backend-progressive-search.ndjson`.
- Backend tests assert byte-equivalent structured fixture content; frontend Vitest parses that same backend-generated NDJSON.
- Removed all score placeholders and renders the score section only when a real value exists.

### I1: separate public and model/tracing projections

- Public event serialization preserves query and fragment components only for validated complete HTTPS booking fields (`booking_url`, `h5_fallback_url`, and `prices[].url`).
- Invalid, relative, and non-HTTPS booking values become `null`.
- Generic non-booking URLs retain the existing query/fragment redaction policy.
- `safe_model_payload` recursively removes all URL/link fields, bare URL values, raw payloads, and keys containing credential markers.
- Tool messages use compact JSON from `safe_model_payload`; graph state keeps the public result separately.
- Existing provider/search tracing continues to emit only route/status/count/latency summaries. URL-free tracing tests were included in the 209-test combined run.

### I2: FlyAI process lifecycle

- Replaced `os.environ.copy()` with a small CLI allowlist plus `FLYAI_API_KEY`.
- Started the CLI in a new POSIX session.
- On timeout, outer cancellation, communication error, nonzero exit, invalid JSON, invalid upstream envelope, or parser error, kills the process group and awaits cleanup.
- Cleans a transient failed attempt before retrying.
- Added deterministic environment, cancellation, timeout, and nonzero-error cleanup tests.

### I3: atomic Ctrip snapshot replacement

- Worker now persists every successful scrape, including `[]`, with explicit provider/route/date scope.
- Repository takes a provider+route+date advisory transaction lock, deletes every prior provider row in that scope, and inserts the new inventory in the same transaction.
- A failure before commit rolls back, preserving the prior inventory.
- Partial refresh tests prove disappeared flights are removed; empty refresh tests prove provider inventory is cleared; provider-isolation tests prove legacy/other-provider rows remain.

### I4: supervised Ctrip browser process

- Moved synchronous Selenium collection into `backend/data_sources/ctrip_browser_worker.py`.
- Parent launches it in a dedicated process session with a minimal environment and no stderr payload forwarding.
- Added an overall collection deadline around retries and a per-process communication deadline.
- Timeout, cancellation, nonzero exit, malformed payload, and communication errors kill the complete process group and await it.
- Added Selenium `set_page_load_timeout(20)` as an inner guard.
- Added a deterministic hanging-process test that does not launch Chrome and asserts `killpg` plus `wait`.
- Ctrip mock fallback now defaults to disabled and remains explicit opt-in only for tests/local use.

### I5: currency propagation and comparison boundaries

- SerpAPI extracts currency from booking details, itinerary/search parameters, and response metadata.
- Ctrip normalized/snapshot rows and provider offers carry currency.
- Normalizer deduplicates and compares only within one currency, preferring query currency when available.
- Repository display and ordering group by currency before numeric amount.
- Recommendation selection, market median, and booking seller selection operate within one chosen currency (CNY when present, otherwise deterministic currency selection).
- Final response analysis uses one primary currency rather than merging unlike values.
- Frontend mapper, chat fallback, discovery rows, and explore cards use propagated currency and `Intl.NumberFormat("zh-CN", {style: "currency"})`.
- Unknown scores, tax, baggage fees, and currency are not fabricated.

### I6: future-only recommendations

- Recommendation pool queries only the next three Shanghai-calendar dates and no longer falls back to historical inventory.
- Cached and newly built cards are filtered again by `depart_date > today` before personalization/pagination.
- Card and booking builders independently reject missing/invalid/past dates.
- Repository `read_deals_latest` is future constrained as defense in depth.

### I7: renderability before pagination

- Backend filters to future cards with a real preview before personalization and slicing.
- `has_more` and `next_offset` are computed from the renderable pool.
- Frontend also follows advancing empty pages until a renderable page or terminal condition, with repeated/non-advancing offset guards.
- Backend and frontend both cover an empty first page followed by a valid later card.

### Duplicate row Minor

- Collapses provider/seller/currency rows deterministically.
- Selection order is priced/fresh, lowest amount within currency, newest parsed timestamp, stable URL.
- Row IDs are deterministic and used as React keys.
- Provider snapshot price IDs include currency.

## GREEN Evidence

### Focused GREEN

- Five self-review lifecycle/currency/secret regressions: `5 passed in 0.15s`.
- Full directly impacted FlyAI/Ctrip/snapshot/recommendation/router files: `58 passed in 3.44s`.
- Repository currency sort node: `1 passed in 0.10s`.
- Frontend nullable wire node: `1 passed` (64 deselected).
- Equal-price freshest dedupe node: `1 passed in 0.01s`.
- Embedded secret-marker sanitizer node: `1 passed in 0.01s`.
- Mock-default node: `1 passed in 0.01s`.
- Standalone non-DB recommendation review file: `4 passed in 0.12s`.

### Combined backend

Command covered flight contracts/fixture, FlyAI, SerpAPI, Ctrip snapshot/source, normalizer, aggregator, worker, graph/router/rendering, tracing, search API/stream API, recommendation review logic, schemas, settings, and dependency manifest.

Result: `209 passed, 1 warning in 19.11s`.

The warning is an existing LangGraph pending-deprecation warning and is unrelated to this change.

### Isolated repository database evidence

The bounded command ran only:

- currency-first sort contract;
- provider rows preserve other providers;
- partial provider refresh replacement;
- empty successful provider refresh replacement;
- historical departure exclusion.

Result: `5 passed in 53.77s` against the isolated test database.

### Frontend

- `npm run lint`: passed (`tsc --noEmit`).
- `npm run test -- --run`: `17 files passed`, `111 tests passed`.
- `npm run build`: Next.js 15.5.15 production build passed; 10 static/dynamic routes generated.

An earlier lint invocation ran concurrently with `next build` and saw transient missing `.next/types` files. It was not counted as green. Serial lint reruns passed before and after the final changes.

### Migrations

Used `dotenv_values("backend/.env")` to load structured values, verified test and production DSNs differ without printing either, then set `DATABASE_URL` only in the child Alembic environment.

- Alembic heads: `1`.
- `alembic -c backend/alembic.ini upgrade head` on the isolated test database: passed within the hard timeout.

### Static and safety checks

- `python3 -m compileall -q backend`: passed.
- `git diff --check`: passed (silent).
- Intended commit scan: 1,808 files scanned (including new fixture/script/report files); one explicit synthetic redaction fixture adjudicated; `0` unapproved credential candidates.
- `backend/.env` and frontend local environment files are not tracked.
- Structured checks confirm `ENABLE_MOCK_FALLBACK=false` in the example and `Settings.enable_mock_fallback` defaults to `False`.
- `CtripSource` also defaults to no mock fallback; the production worker passes `False` explicitly.

## Interrupted Recommendation Run And Limitations

The combined command below was intentionally interrupted and is not counted as green:

```text
pytest -q \
  backend/tests/services/test_recommendation_final_review.py \
  backend/tests/services/test_recommendation_fallback.py \
  backend/tests/services/test_recommendation_feed.py \
  backend/tests/api/test_recommendations_api.py
```

PID `51386` remained for more than eight minutes in the same low-CPU remote asyncpg wait. `SIGINT` returned successfully but the process remained blocked, so `SIGTERM` was sent and the process exited. Recoverable pytest output was exactly 15 completed dots. There was no traceback, failure line, or pytest summary. Therefore:

- the combined recommendation group is inconclusive, not green;
- its 15 dots are not used as pass evidence;
- isolated non-DB recommendation regressions (`4 passed`) provide direct I5/I6/I7 coverage;
- the bounded repository database group (`5 passed`) provides the persistence/future-query evidence;
- frontend full Vitest includes the explore empty-first-page case;
- the remote recommendation API/feed/fallback group was not rerun after interruption to avoid another environment I/O stall.

Per the review instruction, monolithic backend pytest was not rerun against the remote test database. No Docker, live provider, live browser, Railway deployment/configuration, GitHub, or LangSmith live verification is claimed.

## Files Changed

### Backend production

- `backend/.env.example`
- `backend/application/contracts/flight_provider.py`
- `backend/application/graph/nodes/render_response.py`
- `backend/application/graph/nodes/tool_router.py`
- `backend/application/services/flight_offer_normalizer.py`
- `backend/application/services/flight_search_aggregator.py`
- `backend/application/services/recommendation_service.py`
- `backend/application/services/search_events.py`
- `backend/config.py`
- `backend/data_sources/ctrip_browser_worker.py`
- `backend/data_sources/ctrip_source.py`
- `backend/infrastructure/db/flight_snapshot_repo.py`
- `backend/infrastructure/flight_data/providers/ctrip_snapshot.py`
- `backend/infrastructure/flight_data/providers/flyai.py`
- `backend/infrastructure/flight_data/providers/serpapi.py`
- `backend/schemas/common.py`
- `backend/scripts/generate_flight_wire_fixture.py`
- `backend/third_party/flights_monitor/ctrip_api.py`
- `backend/workers/ctrip_refresh.py`

### Backend tests

- `backend/tests/api/test_recommendations_api.py`
- `backend/tests/contracts/test_flight_provider_contracts.py`
- `backend/tests/contracts/test_flight_wire_contract.py`
- `backend/tests/graph/nodes/test_render_response.py`
- `backend/tests/graph/nodes/test_tool_router.py`
- `backend/tests/infra/test_ctrip_snapshot_provider.py`
- `backend/tests/infra/test_flight_snapshot_repo.py`
- `backend/tests/infra/test_flyai_provider.py`
- `backend/tests/infra/test_serpapi_provider.py`
- `backend/tests/services/test_flight_offer_normalizer.py`
- `backend/tests/services/test_flight_search_aggregator.py`
- `backend/tests/services/test_recommendation_fallback.py`
- `backend/tests/services/test_recommendation_feed.py`
- `backend/tests/services/test_recommendation_final_review.py`
- `backend/tests/test_ctrip_source.py`
- `backend/tests/test_dependency_manifest.py`
- `backend/tests/test_schemas.py`
- `backend/tests/test_settings_contract.py`
- `backend/tests/workers/test_ctrip_refresh.py`

### Frontend production and contract artifacts

- `frontend/components/app-shell.tsx`
- `frontend/components/chat-page.tsx`
- `frontend/components/discovery-card-content.tsx`
- `frontend/components/explore-page.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/currency.ts`
- `frontend/lib/mappers.ts`
- `frontend/types/raw.d.ts`
- `frontend/__tests__/api.test.ts`
- `frontend/__tests__/backend-wire-contract.test.ts`
- `frontend/__tests__/component-chat-page.test.tsx`
- `frontend/__tests__/discovery-card-content.test.tsx`
- `frontend/__tests__/explore-page.test.tsx`
- `frontend/__tests__/fixtures/backend-progressive-search.ndjson`
- `frontend/__tests__/mappers.test.ts`

### Report

- `.superpowers/sdd/final-review-fix-report.md`

## Self-Review

The complete diff from `64a913fbac1635e8222c16d195852913f3061f5a` was reviewed after implementation. Follow-up regressions closed nonzero/malformed process cleanup, Ctrip snapshot and recommendation mixed-currency selection, repository mixed-currency ordering, backend-null frontend parsing, freshest duplicate tie-breaking, embedded secret-key markers, and the Ctrip constructor mock default. No remaining Critical or Important finding was identified.

---

# Round 2 Remediation

Review baseline: `aa4f0cdaa1db61dd91f8ba8abeba52e445e71d58`

Date: 2026-07-18

## Root Causes

1. A successful provider refresh was represented only by child snapshot rows. Replacing a route/date with an empty result deleted those rows and erased the fact that an empty refresh had succeeded, so the online provider treated the state as a cache miss and immediately queued it again.
2. The normalizer selected a realtime headline offer but independently marked the cheapest fresh numeric row as `lowest`. A cheaper Ctrip reference snapshot could therefore receive the badge while seller, headline amount, and booking action came from a different row.
3. Repository freshness stopped at the persistence boundary. Recommendation mapping hard-coded row success and defaulted missing freshness to fresh, while the frontend discarded freshness and inferred realtime claims from `lowest` plus a numeric amount.
4. Ctrip browser-worker cleanup ran only on exceptional exits. A successful worker response returned without explicitly killing/reaping the process group, leaving descendant cleanup dependent on the child behaving perfectly.
5. Tightening the wire schema exposed a legacy graph renderer that still emitted the old mock deal shape. That path needed an explicit reference-only projection instead of bypassing the winner/freshness contract.

## RED Evidence

All finding regressions were written and run before their production changes.

### Empty observation and TTL

```text
pytest -q \
  backend/tests/infra/test_flight_snapshot_repo.py::test_empty_provider_observation_is_scoped_and_expires_by_ttl \
  backend/tests/infra/test_ctrip_snapshot_provider.py::test_successful_empty_snapshot_stays_empty_until_its_ttl_expires \
  backend/tests/workers/test_ctrip_refresh.py::test_worker_empty_refresh_is_observed_by_provider_until_ttl_expires
```

Result: `3 failed in 38.83s`. Empty replacements returned no observation age, and both provider paths queued instead of returning a fresh `empty` result.

### One eligible winning row

```text
pytest -q \
  backend/tests/services/test_flight_offer_normalizer.py::test_deduplicates_identity_and_orders_price_rows_stably \
  backend/tests/services/test_flight_offer_normalizer.py::test_price_rows_keep_currency_and_separate_provider_from_price_status \
  backend/tests/test_schemas.py::test_deal_card_rejects_a_winner_that_disagrees_with_the_headline \
  backend/tests/contracts/test_flight_wire_contract.py::test_backend_fixture_preserves_https_deep_link_query_and_currency
```

Result: `4 failed in 0.07s`. The cheaper snapshot row was marked lowest, winner/freshness fields were absent, and the schema accepted contradictory headline/row data.

### Repository-to-recommendation freshness

```text
pytest -q \
  backend/tests/infra/test_flight_snapshot_repo.py::test_read_deals_propagates_expired_and_unknown_price_freshness \
  backend/tests/services/test_recommendation_final_review.py::test_recommendation_pool_cache_version_excludes_pre_freshness_cards \
  backend/tests/services/test_recommendation_final_review.py::test_recommendation_preview_keeps_currency_without_fabricated_score_or_fees \
  backend/tests/services/test_recommendation_final_review.py::test_expired_or_unknown_inventory_is_reference_only
```

Result: `5 failed in 17.72s` (the final node is parametrized). Expired rows appeared fresh, the cache key was still v2, and recommendation cards lacked winner/freshness truth.

### Successful worker cleanup

```text
pytest -q \
  backend/tests/test_ctrip_source.py::test_successful_worker_payload_kills_process_group_and_awaits_cleanup
```

Result: `1 failed`; successful output returned without a process-group kill or awaited cleanup.

### Frontend runtime contract

```text
npm run test -- --run \
  __tests__/backend-wire-contract.test.ts \
  __tests__/api.test.ts \
  __tests__/mappers.test.ts \
  __tests__/discovery-card-content.test.tsx
```

Result: `9 failed | 75 passed`. Runtime parsing did not require winner/freshness, mapping dropped those fields and authoritative total, and the card inferred badges/copy/CTA independently.

### Legacy graph integration

```text
pytest -q \
  backend/tests/graph/test_search_graph.py::test_response_passes_searchresponsedto_validation
```

Result: `1 failed in 1.80s` with 45 DTO validation errors from the pre-contract mock projection. The regression was strengthened to require unknown freshness, no winner, no successful provider row, and no booking URL before changing the renderer.

## Schema And Persistence

Migration `20260718_provider_inventory` adds `provider_inventory_observations` with a composite primary key of provider, origin, destination, and departure date. Each row records non-null `observed_at`, non-null `expires_at`, and checked nonnegative `item_count`.

The observation upsert shares the same transaction and provider/route/date advisory lock as scoped child-row deletion and insertion. Successful nonempty and empty refreshes therefore replace inventory and observation atomically; a failed scrape never enters this transaction and retains prior inventory. No other provider, route, or date is touched.

The committed wire contract now requires:

- `data_freshness` on each price row and deal: `fresh`, `stale`, or `unknown`;
- `winning_price_id` on each deal, nullable when no eligible winner exists;
- exactly one matching fresh, priced, successful row when a winner exists;
- winner identity, seller, currency, amount, total, badge, and booking URL to agree;
- no headline amount, seller, lowest badge, or booking action when no winner exists.

Alembic reports exactly one head: `20260718_provider_inventory`.

## Implementation By Finding

### Important 1: observed empty inventory

- Persisted provider refresh observations for every successful replacement, including `[]`.
- Made fresh empty observations return `ProviderStatus.empty` without enqueueing.
- Made expired empty observations return stale and enqueue one refresh demand.
- Used frozen repository time to prove the exact fresh-to-stale TTL transition and provider/route/date isolation.
- Added worker-to-repository-to-provider coverage for a successful empty scrape.

### Important 2: one winner drives all claims

- Normalizer winner eligibility now requires a realtime, fresh, priced, numeric offer from a successful provider.
- Ctrip `is_realtime=False` rows remain visible references and can never receive `lowest` or drive the headline/CTA.
- Added stable row IDs and `winning_price_id`; only the matching row receives `lowest=true`.
- Added a Pydantic cross-field validator so contradictory backend wire data is rejected.
- Regenerated the committed progressive NDJSON fixture with a cheaper Ctrip snapshot and a more expensive eligible FlyAI winner; backend and frontend tests consume the same artifact.
- Frontend parser validates the winner relationship, mapper preserves it, and the card uses that row alone for headline claims, seller, badge, and booking action.

### Important 3: freshness through recommendation and UI

- Repository derives freshness from each child expiry. Missing expiry is `unknown`; elapsed expiry or stale price status is `stale`; neither can win.
- Recommendation cache advanced to `rec:pool:v3` so older cards cannot bypass the new contract.
- Recommendation cards preserve row/card freshness and explicit winner identity. Nonfresh rows become reference-only with stale provider/price status, no winner, no generated/direct booking URL, no discount claim, and neutral monitoring copy.
- Past, invalid, stale, and unknown inventory cannot create booking actions.
- Frontend displays unknown/stale reference messaging, gates realtime copy and live-price links on fresh status, and gates the CTA on exact card/winner URL agreement.
- Legacy graph mock results now serialize as unknown, disabled reference rows with no winner or URLs.

### Coupled lifecycle Minor

- Ctrip worker process-group termination and `wait()` now run from `finally` on success, timeout, cancellation, malformed output, nonzero exit, and communication failure.
- Deterministic success coverage verifies `SIGKILL` of the process group and awaited reaping without launching a browser.

## GREEN Evidence

### Focused backend

- Directly affected contract/provider/normalizer/recommendation/lifecycle/schema set: `64 passed in 15.35s`.
- Standalone recommendation truthfulness logic: final rerun `7 passed in 0.08s`.
- Successful-worker cleanup node: included in the 64-test set and full Ctrip source coverage.
- Legacy graph DTO/reference projection: final focused rerun `1 passed in 2.13s`.
- Recommendation API authentication boundary: `1 passed, 1 warning in 15.34s`.

### Bounded database and worker evidence

Final six-node Round 2 repository/provider/worker group:

```text
pytest -q \
  backend/tests/infra/test_flight_snapshot_repo.py::test_empty_provider_observation_is_scoped_and_expires_by_ttl \
  backend/tests/infra/test_flight_snapshot_repo.py::test_read_deals_propagates_expired_and_unknown_price_freshness \
  backend/tests/infra/test_flight_snapshot_repo.py::test_provider_refresh_with_empty_success_clears_route_inventory \
  backend/tests/infra/test_flight_snapshot_repo.py::test_mixed_provider_rows_keep_legacy_price_and_freshness \
  backend/tests/infra/test_ctrip_snapshot_provider.py::test_successful_empty_snapshot_stays_empty_until_its_ttl_expires \
  backend/tests/workers/test_ctrip_refresh.py::test_worker_empty_refresh_is_observed_by_provider_until_ttl_expires
```

Result: `6 passed in 104.46s`.

Full Ctrip refresh worker file: `15 passed in 31.09s`.

An earlier full snapshot repository discovery run completed with `15 passed, 2 failed in 252.83s`; both failures were obsolete exact-shape expectations for the newly required row fields and empty observation age. After updating those assertions, the exact two nodes passed in `31.00s`. The final six-node group above is the counted Round 2 DB green result.

### Combined backend

The combined command covered provider contracts, committed wire fixture, query validation, normalizer, aggregator, FlyAI, SerpAPI, Ctrip provider/source, tracing, JSON/stream APIs, graph tool/render/search paths, and schemas.

Final post-self-review result: `188 passed, 1 warning in 20.26s`.

The warning is the existing LangGraph pending-deprecation warning.

### Frontend

- Cross-layer wire/parser/mapper/card group: `4 files passed`, `86 tests passed`.
- Full Vitest: `17 files passed`, `120 tests passed`.
- `npm run lint`: passed (`tsc --noEmit`).
- `npm run build`: Next.js 15.5.15 production build passed and generated all 10 routes.

### Migration, static, and safety

- `alembic -c backend/alembic.ini heads`: one head, `20260718_provider_inventory`.
- Structured `dotenv_values("backend/.env")` check asserted test and production DSNs differ, passed only the test DSN to the Alembic child environment, printed no URL, and upgraded to head successfully.
- `python3 -m compileall -q backend`: passed.
- `git diff --check`: passed.
- Mock-disable contract/default/dependency checks: `20 passed in 0.48s`.
- Local backend/frontend environment files are not tracked.
- The credential-pattern scan covered 1,808 tracked files and printed no values. Its only candidates were pre-existing credential-shaped documentation/test examples in tracked Pydantic source and `test_settings_contract.py`; redacted inspection confirmed they are synthetic. There are zero unadjudicated credential candidates.

## Limitations

The previously interrupted combined recommendation command remains inconclusive and is not counted as green. Its PID `51386` produced exactly 15 dots, no traceback, and no pytest summary before termination after a prolonged remote asyncpg wait. Round 2 did not rerun `test_recommendation_feed.py`, `test_recommendation_fallback.py`, and the DB-backed recommendation API group together. Direct recommendation logic (`7 passed`), the bounded DB group (`6 passed`), search API coverage in the 188-test group, and full frontend explore/card coverage provide isolated evidence without repeating the environment stall.

The monolithic backend suite was not run against the remote test database. No paid/live provider, live browser, Docker, Railway, GitHub, LangSmith, or deployment verification was performed or claimed.

## Round 2 Files Changed

### Backend production and migration

- `backend/db/migrations/versions/20260718_provider_inventory_observations.py`
- `backend/application/graph/nodes/render_response.py`
- `backend/application/services/flight_offer_normalizer.py`
- `backend/application/services/recommendation_service.py`
- `backend/data_sources/ctrip_source.py`
- `backend/infrastructure/db/flight_snapshot_repo.py`
- `backend/infrastructure/flight_data/providers/ctrip_snapshot.py`
- `backend/schemas/common.py`
- `backend/scripts/generate_flight_wire_fixture.py`

### Backend tests

- `backend/tests/contracts/test_flight_wire_contract.py`
- `backend/tests/graph/test_search_graph.py`
- `backend/tests/infra/test_ctrip_snapshot_provider.py`
- `backend/tests/infra/test_flight_snapshot_repo.py`
- `backend/tests/services/test_flight_offer_normalizer.py`
- `backend/tests/services/test_recommendation_final_review.py`
- `backend/tests/test_ctrip_source.py`
- `backend/tests/test_schemas.py`
- `backend/tests/workers/test_ctrip_refresh.py`

### Frontend production, tests, and fixture

- `frontend/components/app-shell.tsx`
- `frontend/components/discovery-card-content.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/mappers.ts`
- `frontend/__tests__/api.test.ts`
- `frontend/__tests__/backend-wire-contract.test.ts`
- `frontend/__tests__/component-chat-page.test.tsx`
- `frontend/__tests__/discovery-card-content.test.tsx`
- `frontend/__tests__/explore-page.test.tsx`
- `frontend/__tests__/fixtures/backend-progressive-search.ndjson`
- `frontend/__tests__/mappers.test.ts`

### Report

- `.superpowers/sdd/final-review-fix-report.md`

## Self-Review Follow-Ups

The complete diff review found and closed three cross-contract gaps before commit:

1. `h5_fallback_url` could survive without a winner or disagree with the winner. Backend RED: `1 failed in 0.06s`; GREEN: `1 passed in 0.01s`. Frontend RED: `1 failed` with 70 skipped; GREEN: `1 passed` with 70 skipped.
2. The frontend accepted an omitted card `booking_url` when the winning row exposed one, while Pydantic rejected it. RED: `1 failed` with 71 skipped; GREEN: `1 passed` with 71 skipped.
3. Unknown reference-only legacy graph deals still received a numeric score. RED: `1 failed in 2.06s`; GREEN: `1 passed in 2.13s`. The first combined rerun then caught an over-broad gate affecting old cache payloads (`1 failed, 187 passed`); narrowing the gate to explicit winner/freshness fields produced `3 passed` focused and the final `188 passed` combined result.

No Critical or Important issue remained after the final diff pass.

## Round 2 Self-Review And Commit

The complete diff from `aa4f0cdaa1db61dd91f8ba8abeba52e445e71d58` was reviewed after implementation and verification. The final commit uses the required message `fix(flights): preserve snapshot truthfulness`. Its exact hash is reported beside this report after Git creates the commit; a commit cannot contain its own final hash because changing this file changes that hash.
