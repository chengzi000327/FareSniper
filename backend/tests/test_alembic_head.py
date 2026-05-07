"""Lock the alembic chain head.

Uses ``python -m alembic`` so the test honours whichever Python runs it,
which matches how the CI / Railway image actually invokes Alembic.
"""
from __future__ import annotations

import subprocess
import sys


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
    )
    assert "(head)" in proc.stdout
