"""create v_monthly_qpc and v_search_funnel views.

Revision ID: 20260507_metrics_views
Revises: 20260506_analytics_events
Create Date: 2026-05-07 00:00:00.000000
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "20260507_metrics_views"
down_revision: Union[str, Sequence[str], None] = "20260506_analytics_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# versions/<file>.py → migrations/ → db/ → backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SQL_PATH = _BACKEND_ROOT / "analytics" / "metrics_views.sql"


def _split_statements(sql: str) -> list[str]:
    """Split a sql script into individual statements.

    asyncpg's prepared-statement layer rejects multi-statement strings, so
    each ``CREATE OR REPLACE VIEW`` block is run separately. Comment-only
    chunks and empty trailing pieces are filtered out.
    """
    out: list[str] = []
    for chunk in sql.split(";"):
        stripped = "\n".join(
            line for line in chunk.splitlines() if not line.strip().startswith("--")
        ).strip()
        if stripped:
            out.append(stripped)
    return out


def upgrade() -> None:
    for stmt in _split_statements(_SQL_PATH.read_text()):
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_search_funnel")
    op.execute("DROP VIEW IF EXISTS v_monthly_qpc")
