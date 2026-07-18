from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import sqlalchemy as sa


MIGRATION_DIR = Path("backend/db/migrations/versions")


def _load_migration(filename: str) -> ModuleType:
    path = MIGRATION_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SchemaInspector:
    def __init__(self, tables: dict[str, dict[str, Any]]) -> None:
        self.tables = tables

    def get_table_names(self) -> list[str]:
        return list(self.tables)

    def get_columns(self, table_name: str) -> list[dict[str, str]]:
        return [
            {"name": name}
            for name in sorted(self.tables[table_name].get("columns", set()))
        ]

    def get_indexes(self, table_name: str) -> list[dict[str, str]]:
        return [
            {"name": name}
            for name in sorted(self.tables[table_name].get("indexes", set()))
        ]

    def get_check_constraints(self, table_name: str) -> list[dict[str, str]]:
        return [dict(check) for check in self.tables[table_name].get("checks", [])]


class RecordingOperations:
    def __init__(self, tables: dict[str, dict[str, Any]]) -> None:
        self.bind = object()
        self.calls: list[tuple[Any, ...]] = []
        self.tables = tables

    def get_bind(self) -> object:
        return self.bind

    def add_column(self, table_name: str, column: sa.Column[Any]) -> None:
        self.calls.append(("add_column", table_name, column.name))
        self.tables[table_name].setdefault("columns", set()).add(column.name)

    def create_index(
        self, name: str, table_name: str, columns: list[str]
    ) -> None:
        self.calls.append(("create_index", name, table_name, tuple(columns)))
        self.tables[table_name].setdefault("indexes", set()).add(name)

    def create_table(self, table_name: str, *items: Any) -> None:
        self.calls.append(("create_table", table_name, items))
        self.tables[table_name] = {
            "columns": {
                item.name for item in items if isinstance(item, sa.Column)
            },
            "indexes": set(),
            "checks": [
                {"name": item.name, "sqltext": str(item.sqltext)}
                for item in items
                if isinstance(item, sa.CheckConstraint)
            ],
            "rows": [],
        }

    def create_check_constraint(
        self, name: str, table_name: str, condition: str
    ) -> None:
        self.calls.append(("create_check_constraint", name, table_name, condition))
        self.tables[table_name].setdefault("checks", []).append(
            {"name": name, "sqltext": condition}
        )

    def drop_index(self, name: str, *, table_name: str) -> None:
        self.calls.append(("drop_index", name, table_name))
        self.tables[table_name].setdefault("indexes", set()).discard(name)

    def drop_table(self, table_name: str) -> None:
        self.calls.append(("drop_table", table_name))
        self.tables.pop(table_name, None)

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.calls.append(("drop_column", table_name, column_name))
        self.tables[table_name].setdefault("columns", set()).discard(column_name)


@pytest.fixture
def provider_migration() -> ModuleType:
    return _load_migration("20260716_provider_snapshots.py")


@pytest.fixture
def inventory_migration() -> ModuleType:
    return _load_migration("20260718_provider_inventory_observations.py")


def _install_schema(
    monkeypatch: pytest.MonkeyPatch,
    migration: ModuleType,
    tables: dict[str, dict[str, Any]],
) -> RecordingOperations:
    operations = RecordingOperations(tables)
    inspector = SchemaInspector(tables)
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    return operations


def test_provider_upgrade_repairs_only_missing_parts_of_precreated_schema(
    monkeypatch: pytest.MonkeyPatch, provider_migration: ModuleType
) -> None:
    schema: dict[str, dict[str, Any]] = {
        "platform_price_snapshots": {
            "columns": {"flight_snapshot_id", "data_provider", "price_status"},
            "indexes": set(),
        },
        "flight_search_demands": {
            "columns": {"id"},
            "indexes": set(),
            "rows": [{"id": "existing-demand"}],
        },
    }
    operations = _install_schema(
        monkeypatch,
        provider_migration,
        schema,
    )

    provider_migration.upgrade()

    assert operations.calls == [
        ("add_column", "platform_price_snapshots", "currency"),
        ("add_column", "platform_price_snapshots", "expires_at"),
        (
            "create_index",
            "ix_platform_price_provider_flight",
            "platform_price_snapshots",
            ("data_provider", "flight_snapshot_id"),
        ),
        (
            "create_index",
            "ix_flight_search_demands_due",
            "flight_search_demands",
            ("active", "next_run_at", "priority"),
        ),
    ]
    assert schema["flight_search_demands"]["rows"] == [
        {"id": "existing-demand"}
    ]


def test_provider_upgrade_is_noop_when_precreated_schema_is_complete(
    monkeypatch: pytest.MonkeyPatch, provider_migration: ModuleType
) -> None:
    operations = _install_schema(
        monkeypatch,
        provider_migration,
        {
            "platform_price_snapshots": {
                "columns": {
                    "flight_snapshot_id",
                    "data_provider",
                    "currency",
                    "price_status",
                    "expires_at",
                },
                "indexes": {"ix_platform_price_provider_flight"},
            },
            "flight_search_demands": {
                "columns": {"id"},
                "indexes": {"ix_flight_search_demands_due"},
            },
        },
    )

    provider_migration.upgrade()

    assert operations.calls == []


def test_provider_upgrade_creates_missing_demand_table_and_due_index(
    monkeypatch: pytest.MonkeyPatch, provider_migration: ModuleType
) -> None:
    operations = _install_schema(
        monkeypatch,
        provider_migration,
        {
            "platform_price_snapshots": {
                "columns": {
                    "flight_snapshot_id",
                    "data_provider",
                    "currency",
                    "price_status",
                    "expires_at",
                },
                "indexes": {"ix_platform_price_provider_flight"},
            }
        },
    )

    provider_migration.upgrade()

    assert [call[:2] for call in operations.calls] == [
        ("create_table", "flight_search_demands"),
        ("create_index", "ix_flight_search_demands_due"),
    ]


def test_inventory_upgrade_adds_only_missing_check_to_precreated_table(
    monkeypatch: pytest.MonkeyPatch, inventory_migration: ModuleType
) -> None:
    schema: dict[str, dict[str, Any]] = {
        "provider_inventory_observations": {
            "columns": {"provider", "item_count"},
            "checks": [],
            "rows": [{"provider": "ctrip", "item_count": 0}],
        }
    }
    operations = _install_schema(
        monkeypatch,
        inventory_migration,
        schema,
    )

    inventory_migration.upgrade()

    assert operations.calls == [
        (
            "create_check_constraint",
            "ck_provider_inventory_observation_item_count",
            "provider_inventory_observations",
            "item_count >= 0",
        )
    ]
    assert schema["provider_inventory_observations"]["rows"] == [
        {"provider": "ctrip", "item_count": 0}
    ]
    assert schema["provider_inventory_observations"]["checks"] == [
        {
            "name": "ck_provider_inventory_observation_item_count",
            "sqltext": "item_count >= 0",
        }
    ]


@pytest.mark.parametrize(
    "sqltext",
    [
        "item_count >= 0",
        "(item_count >= 0)",
        '((("item_count") >= (0)::integer))',
        "0 <= item_count",
        '(("item_count")) >= (((0)::smallint))',
        '((0)::numeric(1, 0)) <= (("item_count"))',
    ],
)
def test_inventory_upgrade_accepts_equivalent_named_check_definitions(
    monkeypatch: pytest.MonkeyPatch,
    inventory_migration: ModuleType,
    sqltext: str,
) -> None:
    operations = _install_schema(
        monkeypatch,
        inventory_migration,
        {
            "provider_inventory_observations": {
                "columns": {"provider", "item_count"},
                "checks": [
                    {
                        "name": "ck_provider_inventory_observation_item_count",
                        "sqltext": sqltext,
                    }
                ],
            }
        },
    )

    inventory_migration.upgrade()

    assert operations.calls == []


@pytest.mark.parametrize(
    "sqltext",
    [
        "item_count >= -1",
        "item_count::smallint >= 0",
        "item_count::numeric(1, 0) >= 0",
    ],
)
def test_inventory_upgrade_rejects_mismatched_named_check_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    inventory_migration: ModuleType,
    sqltext: str,
) -> None:
    schema: dict[str, dict[str, Any]] = {
        "provider_inventory_observations": {
            "columns": {"provider", "item_count"},
            "checks": [
                {
                    "name": "ck_provider_inventory_observation_item_count",
                    "sqltext": sqltext,
                }
            ],
            "rows": [{"provider": "ctrip", "item_count": 0}],
        }
    }
    before = deepcopy(schema)
    operations = _install_schema(monkeypatch, inventory_migration, schema)

    with pytest.raises(RuntimeError, match="mismatched definition"):
        inventory_migration.upgrade()

    assert operations.calls == []
    assert schema == before


def test_inventory_upgrade_creates_fresh_table_with_named_check(
    monkeypatch: pytest.MonkeyPatch, inventory_migration: ModuleType
) -> None:
    operations = _install_schema(monkeypatch, inventory_migration, {})

    inventory_migration.upgrade()

    assert len(operations.calls) == 1
    action, table_name, items = operations.calls[0]
    assert action == "create_table"
    assert table_name == "provider_inventory_observations"
    assert any(
        isinstance(item, sa.CheckConstraint)
        and item.name == "ck_provider_inventory_observation_item_count"
        for item in items
    )


def test_provider_downgrade_aborts_without_touching_precreated_schema_or_rows(
    monkeypatch: pytest.MonkeyPatch, provider_migration: ModuleType
) -> None:
    schema: dict[str, dict[str, Any]] = {
        "platform_price_snapshots": {
            "columns": {
                "flight_snapshot_id",
                "data_provider",
                "currency",
                "price_status",
                "expires_at",
            },
            "indexes": {"ix_platform_price_provider_flight"},
            "rows": [{"id": "existing-price", "data_provider": "legacy"}],
        },
        "flight_search_demands": {
            "columns": {"id", "active", "next_run_at", "priority"},
            "indexes": {"ix_flight_search_demands_due"},
            "rows": [{"id": "existing-demand"}],
        },
    }
    before = deepcopy(schema)
    operations = _install_schema(monkeypatch, provider_migration, schema)

    provider_migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        provider_migration.downgrade()

    assert operations.calls == []
    assert schema == before


def test_inventory_downgrade_aborts_without_touching_precreated_schema_or_rows(
    monkeypatch: pytest.MonkeyPatch, inventory_migration: ModuleType
) -> None:
    schema: dict[str, dict[str, Any]] = {
        "provider_inventory_observations": {
            "columns": {
                "provider",
                "origin_code",
                "destination_code",
                "depart_date",
                "observed_at",
                "expires_at",
                "item_count",
            },
            "checks": [
                {
                    "name": "ck_provider_inventory_observation_item_count",
                    "sqltext": "(item_count >= 0)",
                }
            ],
            "rows": [{"provider": "ctrip", "item_count": 0}],
        }
    }
    before = deepcopy(schema)
    operations = _install_schema(monkeypatch, inventory_migration, schema)

    inventory_migration.upgrade()
    with pytest.raises(RuntimeError, match="irreversible"):
        inventory_migration.downgrade()

    assert operations.calls == []
    assert schema == before


@pytest.mark.parametrize(
    ("migration_fixture", "filename"),
    [
        ("provider_migration", "20260716_provider_snapshots.py"),
        (
            "inventory_migration",
            "20260718_provider_inventory_observations.py",
        ),
    ],
)
def test_downgrade_aborts_before_touching_an_empty_schema(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    migration_fixture: str,
    filename: str,
) -> None:
    migration = request.getfixturevalue(migration_fixture)
    assert migration.__file__ is not None
    assert migration.__file__.endswith(filename)
    operations = _install_schema(monkeypatch, migration, {})

    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()

    assert operations.calls == []
