"""Lock the alembic chain head.

Uses ``python -m alembic`` so the test honours whichever Python runs it,
which matches how the CI / Railway image actually invokes Alembic.
"""
from __future__ import annotations

import os
import subprocess
import sys

from backend.config import settings


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
    )
    assert "(head)" in proc.stdout


def test_alembic_has_exactly_one_head():
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "heads"],
        capture_output=True,
        text=True,
        check=True,
    )
    heads = [line for line in proc.stdout.splitlines() if "(head)" in line]
    assert heads == ["20260716_provider_snapshots (head)"]
