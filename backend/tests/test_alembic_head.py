"""Lock the alembic chain head.

Uses ``python -m alembic`` so the test honours whichever Python runs it,
which matches how the CI / Railway image actually invokes Alembic.
"""
from __future__ import annotations

import ast
import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import insert, text

from backend.config import settings
from backend.infrastructure.db.flight_demand_repo import (
    CollectorNodeRow,
    FlightSearchDemandRow,
)
from backend.infrastructure.db.flight_snapshot_repo import PlatformPriceSnapshot


def _test_database_env() -> dict[str, str]:
    assert settings.test_database_url
    assert settings.test_database_url != settings.database_url
    raw_test_database_url = settings.test_database_url.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    assert raw_test_database_url != settings.test_database_url
    return {**os.environ, "DATABASE_URL": raw_test_database_url}


def test_alembic_history_lists_init():
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "history"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert "20260505_init" in proc.stdout
    assert "a1b2c3d4e5f6" in proc.stdout


def test_alembic_current_is_at_head():
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "current"],
        capture_output=True,
        text=True,
        check=True,
        env=_test_database_env(),
        timeout=30,
    )
    assert "(head)" in proc.stdout


def test_alembic_has_exactly_one_head():
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "heads"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    heads = [line for line in proc.stdout.splitlines() if "(head)" in line]
    assert heads == ["20260718_ctrip_collector (head)"]


def test_alembic_registers_task4_repositories():
    env_path = Path("backend/db/migrations/env.py")
    module = ast.parse(env_path.read_text())
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_REPO_MODULES"
            for target in node.targets
        )
    )
    repositories = ast.literal_eval(assignment.value)

    assert "backend.infrastructure.db.flight_snapshot_repo" in repositories
    assert "backend.infrastructure.db.flight_demand_repo" in repositories


def test_demand_metadata_matches_migration_keys():
    table = FlightSearchDemandRow.__table__
    constraint = next(
        item
        for item in table.constraints
        if item.name == "uq_flight_search_demand_hour"
    )
    index = next(
        item
        for item in table.indexes
        if item.name == "ix_flight_search_demands_due"
    )

    assert [column.name for column in constraint.columns] == [
        "origin_code",
        "destination_code",
        "depart_date",
        "demand_hour",
    ]
    assert [column.name for column in index.columns] == [
        "active",
        "status",
        "next_attempt_at",
        "priority",
    ]

    assert {
        "status",
        "attempts",
        "next_attempt_at",
        "lease_owner",
        "lease_expires_at",
        "last_error",
        "created_at",
        "updated_at",
    } <= set(table.columns.keys())


def test_collector_node_metadata_matches_migration():
    assert list(CollectorNodeRow.__table__.columns.keys()) == [
        "node_id",
        "version",
        "status",
        "last_heartbeat",
        "last_success",
    ]


def test_platform_price_metadata_matches_provider_index():
    index = next(
        item
        for item in PlatformPriceSnapshot.__table__.indexes
        if item.name == "ix_platform_price_provider_flight"
    )

    assert [column.name for column in index.columns] == [
        "data_provider",
        "flight_snapshot_id",
    ]
    seller_key = next(
        item
        for item in PlatformPriceSnapshot.__table__.constraints
        if item.name == "uq_platform_price_provider_seller"
    )
    assert [column.name for column in seller_key.columns] == [
        "flight_snapshot_id",
        "data_provider",
        "platform",
    ]


@pytest.mark.asyncio
async def test_collector_downgrade_consolidates_hourly_route_state(seeded_pg):
    current_request = datetime(2099, 7, 1, 12, 45, tzinfo=timezone.utc)
    older_request = current_request - timedelta(hours=1)
    common = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "attempts": 0,
        "lease_owner": None,
        "lease_expires_at": None,
        "last_error": None,
        "status": "pending",
    }
    async with seeded_pg.begin() as connection:
        await connection.execute(
            insert(FlightSearchDemandRow),
            [
                {
                    **common,
                    "id": "older-high-priority",
                    "demand_hour": older_request.replace(
                        minute=0, second=0, microsecond=0
                    ),
                    "priority": 100,
                    "source": "price_alert",
                    "last_requested_at": older_request,
                    "next_run_at": current_request + timedelta(hours=3),
                    "next_attempt_at": current_request + timedelta(hours=3),
                    "expires_at": current_request + timedelta(days=2),
                    "active": False,
                    "created_at": older_request,
                    "updated_at": older_request,
                },
                {
                    **common,
                    "id": "current-low-priority",
                    "demand_hour": current_request.replace(
                        minute=0, second=0, microsecond=0
                    ),
                    "priority": 5,
                    "source": "hot_route",
                    "last_requested_at": current_request,
                    "next_run_at": current_request + timedelta(hours=1),
                    "next_attempt_at": current_request + timedelta(hours=1),
                    "expires_at": current_request + timedelta(days=5),
                    "active": True,
                    "created_at": current_request,
                    "updated_at": current_request,
                },
            ],
        )

    await seeded_pg.dispose()
    try:
        await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "downgrade",
                "20260718_provider_inventory",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=_test_database_env(),
            timeout=30,
        )
        await seeded_pg.dispose()
        async with seeded_pg.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT id, priority, source, active, expires_at,
                               next_run_at, last_requested_at
                        FROM flight_search_demands
                        WHERE origin_code = 'BJS'
                          AND destination_code = 'SHA'
                          AND depart_date = '2099-08-01'
                        """
                    )
                )
            ).one()

        assert row.id == "current-low-priority"
        assert row.priority == 100
        assert row.source == "price_alert"
        assert row.active is True
        assert row.expires_at == current_request + timedelta(days=5)
        assert row.next_run_at == current_request + timedelta(hours=1)
        assert row.last_requested_at == current_request
    finally:
        await seeded_pg.dispose()
        await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "upgrade",
                "head",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=_test_database_env(),
            timeout=30,
        )
        await seeded_pg.dispose()
