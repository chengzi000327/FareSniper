# Deployment Migration Hardening Report

## Status

`DONE_WITH_CONCERNS`

Implementation commit:
`4801b6ac141b4b65cf752b29ba9a7a0312d52886`

Base commit:
`9ba056ef7ab0c99dab6c2427beee2a48da85bf4e`

Branch:
`codex/deployment-migration-hardening`

No Railway environment, production system, secrets, production URL, or database
was accessed or modified.

## Implementation

- `20260716_provider_snapshots.py` now reflects the current schema and adds
  each provider column only when absent.
- It creates `ix_platform_price_provider_flight` and
  `ix_flight_search_demands_due` only when absent.
- It creates `flight_search_demands` only when absent. An existing table is not
  recreated, renamed, truncated, rewritten, or otherwise subjected to a row
  operation.
- `20260718_provider_inventory_observations.py` creates the full table and named
  non-negative `item_count` check on a fresh schema.
- When the inventory table already exists, it is preserved and only the missing
  named check constraint is added.
- Downgrades inspect before dropping and become no-ops when their owned schema
  objects are already absent.

## TDD Evidence

### RED

The focused tests were written before either production migration was edited.

Command:

```bash
python3 -m pytest -q backend/tests/migrations/test_provider_migration_hardening.py
```

Observed output:

```text
FFFFF.FF                                                                 [100%]
7 failed, 1 passed in 0.12s
```

The seven expected failures demonstrated:

- duplicate provider-column additions on partially and fully pre-created
  schemas;
- duplicate provider and demand index creation;
- recreation of an existing `flight_search_demands` table;
- recreation of an existing `provider_inventory_observations` table instead of
  adding its missing named check;
- recreation when the named check was already present; and
- unconditional downgrade operations when owned objects were absent.

### GREEN

Command after the minimal production edits:

```bash
python3 -m pytest -q backend/tests/migrations/test_provider_migration_hardening.py
```

Observed output:

```text
........                                                                 [100%]
8 passed in 0.09s
```

The fake Alembic operation recorder models rows on pre-created tables; a
duplicate `create_table` replaces those modeled rows. The GREEN preservation
assertions therefore verify that the existing-table paths do not recreate the
tables or alter the modeled rows.

## Verification

### Focused and relevant non-database backend tests

Command:

```bash
DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper' \
TEST_DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper_test' \
python3 -m pytest -q \
  backend/tests/migrations/test_provider_migration_hardening.py \
  backend/tests/test_railway_config.py \
  backend/tests/test_dependency_manifest.py \
  backend/tests/infra/test_db_single_source.py \
  backend/tests/infra/test_db_base.py::test_base_metadata_exposed \
  backend/tests/infra/test_db_base.py::test_engine_is_async
```

The dummy localhost URLs permit model imports only. This test selection does
not connect to a database.

Observed output:

```text
..........................                                               [100%]
26 passed in 0.12s
```

### Existing Alembic head/static migration tests

Command:

```bash
DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper' \
TEST_DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper_test' \
python3 -m pytest -q \
  backend/tests/test_alembic_head.py::test_alembic_history_lists_init \
  backend/tests/test_alembic_head.py::test_alembic_has_exactly_one_head \
  backend/tests/test_alembic_head.py::test_alembic_registers_task4_repositories \
  backend/tests/test_alembic_head.py::test_demand_metadata_matches_migration_keys \
  backend/tests/test_alembic_head.py::test_platform_price_metadata_matches_provider_index
```

Observed output:

```text
.F...                                                                    [100%]
FAILED backend/tests/test_alembic_head.py::test_alembic_has_exactly_one_head
1 failed, 4 passed in 0.42s
```

The failure is pre-existing at the required base commit. The assertion expects
`20260716_provider_snapshots (head)`, while the already-committed inventory
migration makes the actual single head:

```bash
python3 -m alembic -c backend/alembic.ini heads
```

```text
20260718_provider_inventory (head)
```

`backend/tests/test_alembic_head.py` was not changed because this task's owned
test scope was limited to focused migration-hardening tests.

### Static checks

Commands:

```bash
python3 -m py_compile \
  backend/db/migrations/versions/20260716_provider_snapshots.py \
  backend/db/migrations/versions/20260718_provider_inventory_observations.py \
  backend/tests/migrations/test_provider_migration_hardening.py
git diff --check
```

Observed output: both commands exited `0` with no output.

`black` and `ruff` were not installed in the available Python environment, so
no formatter/linter result is claimed.

Database-backed migration and repository tests were not run because the task
explicitly prohibited modifying a database. No `alembic current`, `stamp`,
`upgrade`, or `downgrade` command was executed.

## Changed Files

- `backend/tests/migrations/test_provider_migration_hardening.py`
- `backend/db/migrations/versions/20260716_provider_snapshots.py`
- `backend/db/migrations/versions/20260718_provider_inventory_observations.py`
- `.superpowers/sdd/deployment-migration-hardening-report.md`

## Self-Review

- Confirmed every provider column is gated independently by reflected column
  names.
- Confirmed both required indexes are gated independently by reflected index
  names.
- Confirmed both early-created table paths avoid `create_table` and preserve
  modeled rows.
- Confirmed the inventory repair checks the exact required constraint name and
  creates only that check when missing.
- Confirmed fresh inventory creation still includes the named non-negative
  check.
- Confirmed no row SQL, table rename, truncation, credential, URL, or production
  data was added.
- Confirmed downgrades touch only objects from their revisions and guard absent
  objects.
- Reviewed the scoped diff against all requirements and found no unaddressed
  implementation requirement.

## Concerns

1. The existing Alembic head test is stale and remains red: it expects the
   previous revision even though the repository has exactly one newer head.
2. No PostgreSQL-backed migration execution was performed because the task
   prohibited database modification. Verification is pure unit/static plus
   non-connecting backend tests.
3. As with the prior migrations, downgrade reflection can determine whether an
   object exists but cannot determine whether Alembic or an earlier
   `Base.metadata.create_all()` originally created it. The recovery procedure
   is upgrade-only; a downgrade would still reverse present revision objects.

## Independent Review Fix

This addendum records the follow-up patch for all four findings in
`.superpowers/sdd/deployment-migration-hardening-review.md`. It supersedes
Concern 3 above: both provider revision downgrades are now explicitly
irreversible and abort before obtaining a bind, inspecting schema, or issuing
any Alembic operation.

### Resolution

- `20260716_provider_snapshots.downgrade()` raises immediately, preventing both
  destructive DDL and an Alembic revision decrement.
- `20260718_provider_inventory_observations.downgrade()` raises immediately for
  the same reason.
- Focused upgrade-then-downgrade tests use populated pre-created demand,
  platform-price, and inventory schemas. They assert the exception, zero
  Alembic operations, and exact deep equality of schema and rows.
- Inventory check reflection now compares both the exact required name and its
  `sqltext` definition.
- Equivalent non-negative forms are accepted after bounded normalization of
  whitespace, parentheses, identifier quoting, common integer/numeric casts,
  and comparison direction.
- A required-name check with any other definition raises before schema or row
  mutation. An absent required-name check is still created normally.

### Review-Fix RED

The new regression tests were run before either production migration was
edited.

Command:

```bash
python3 -m pytest -q backend/tests/migrations/test_provider_migration_hardening.py
```

Observed output:

```text
........F.FFFF                                                           [100%]
FAILED backend/tests/migrations/test_provider_migration_hardening.py::test_inventory_upgrade_rejects_mismatched_named_check_without_mutation
FAILED backend/tests/migrations/test_provider_migration_hardening.py::test_provider_downgrade_aborts_without_touching_precreated_schema_or_rows
FAILED backend/tests/migrations/test_provider_migration_hardening.py::test_inventory_downgrade_aborts_without_touching_precreated_schema_or_rows
FAILED backend/tests/migrations/test_provider_migration_hardening.py::test_downgrade_aborts_before_touching_an_empty_schema[provider_migration-20260716_provider_snapshots.py]
FAILED backend/tests/migrations/test_provider_migration_hardening.py::test_downgrade_aborts_before_touching_an_empty_schema[inventory_migration-20260718_provider_inventory_observations.py]
5 failed, 9 passed in 0.13s
```

The failures were the intended missing behavior: mismatched constraint SQL did
not raise, and both downgrades still executed instead of aborting.

### Review-Fix GREEN

Command:

```bash
python3 -m pytest -q --tb=no backend/tests/migrations/test_provider_migration_hardening.py
```

Exact output:

```text
..............                                                           [100%]
14 passed in 0.08s
```

### Alembic Static Tests

Command:

```bash
DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper' \
TEST_DATABASE_URL='postgresql+asyncpg://test:test@127.0.0.1:1/faresniper_test' \
python3 -m pytest -q --tb=no \
  backend/tests/test_alembic_head.py::test_alembic_history_lists_init \
  backend/tests/test_alembic_head.py::test_alembic_has_exactly_one_head \
  backend/tests/test_alembic_head.py::test_alembic_registers_task4_repositories \
  backend/tests/test_alembic_head.py::test_demand_metadata_matches_migration_keys \
  backend/tests/test_alembic_head.py::test_platform_price_metadata_matches_provider_index
```

Exact output:

```text
.F...                                                                    [100%]
=========================== short test summary info ============================
FAILED backend/tests/test_alembic_head.py::test_alembic_has_exactly_one_head
1 failed, 4 passed in 0.39s
```

The same pre-existing stale assertion remains: it expects
`20260716_provider_snapshots (head)`, while the repository's actual single head
is `20260718_provider_inventory (head)`. The static test file is outside this
review-fix scope.

### Static Checks

Commands:

```bash
python3 -m py_compile \
  backend/db/migrations/versions/20260716_provider_snapshots.py \
  backend/db/migrations/versions/20260718_provider_inventory_observations.py \
  backend/tests/migrations/test_provider_migration_hardening.py
git diff --check
```

Exact output: no output; both commands exited `0`.

### Review-Fix Self-Review

- Confirmed each downgrade's first and only statement is an exception, so no
  DDL, row operation, schema inspection, or version decrement can occur.
- Confirmed upgrade-then-downgrade regression tests preserve populated
  pre-created schema and rows byte-for-byte at the modeled state level.
- Confirmed correct, missing, and mismatched exact-name constraint definitions
  have focused coverage.
- Confirmed a mismatched definition records zero Alembic operations and leaves
  rows and schema unchanged.
- Confirmed normalization rejects `item_count >= -1` and accepts reflected
  parenthesized, quoted, cast, and reversed equivalent forms.
- Confirmed the patch contains no credentials, deployment URLs, production
  data, or database-facing command.

### Remaining Concerns

1. The unrelated Alembic head assertion remains stale and red.
2. PostgreSQL-backed execution was not run because database modification was
   explicitly prohibited. All review-fix verification is pure unit/static and
   non-connecting.
