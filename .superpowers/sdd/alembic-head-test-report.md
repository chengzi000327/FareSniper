# Alembic Head Test Contract

- Base commit: `9ba056ef7ab0c99dab6c2427beee2a48da85bf4e`
- Actual sole head: `20260718_provider_inventory`
- Correction: updated the stale expected head in `backend/tests/test_alembic_head.py`.
- Red evidence: the focused test failed because the test expected `20260716_provider_snapshots (head)` while Alembic reported `20260718_provider_inventory (head)`.
- Verification: focused test passed (`1 passed`). The complete `backend/tests/test_alembic_head.py` file ran with PostgreSQL-shaped URLs and reported `5 passed, 1 failed`; the remaining failure is the database-backed current-head check because no PostgreSQL service is listening on `127.0.0.1:5432`.
- Note: `python` was unavailable; commands used `python3`. The SQLite rerun was not suitable for the full file because the test explicitly requires PostgreSQL URL normalization.
