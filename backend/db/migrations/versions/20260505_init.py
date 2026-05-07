"""launch-plan canonical schema base revision.

Acts as a no-op anchor between the legacy v1.1 head ``a1b2c3d4e5f6`` and
the canonical analytics / feature-flag / users / etc. revisions added in
TG-03 onwards. Keeping it as a no-op keeps the chain linear and avoids a
multi-base graph when the launch-plan revisions land out of plan order.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260505_init"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT 1")


def downgrade() -> None:
    pass
