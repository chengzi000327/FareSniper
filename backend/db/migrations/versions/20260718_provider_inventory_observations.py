"""Add provider inventory refresh observations.

Revision ID: 20260718_provider_inventory
Revises: 20260716_provider_snapshots
Create Date: 2026-07-18 00:00:00.000000
"""
from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_provider_inventory"
down_revision: Union[str, Sequence[str], None] = "20260716_provider_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ITEM_COUNT_CHECK_NAME = "ck_provider_inventory_observation_item_count"
_COMPARISON_RE = re.compile(
    r"^(?P<left>.+?)(?P<operator>>=|<=)(?P<right>.+)$"
)
_ZERO_CAST_RE = re.compile(
    r"^(?P<operand>.+)::"
    r"(?:smallint|integer|bigint|numeric(?:\(\d+(?:,\d+)?\))?)$"
)


def _strip_outer_parentheses(expression: str) -> str:
    while expression.startswith("(") and expression.endswith(")"):
        depth = 0
        for index, character in enumerate(expression):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    if index != len(expression) - 1:
                        return expression
                    expression = expression[1:-1]
                    break
                if depth < 0:
                    return expression
        else:
            return expression
    return expression


def _is_item_count_operand(expression: str) -> bool:
    return _strip_outer_parentheses(expression) == "item_count"


def _is_zero_operand(expression: str) -> bool:
    expression = _strip_outer_parentheses(expression)
    while cast_match := _ZERO_CAST_RE.fullmatch(expression):
        expression = _strip_outer_parentheses(cast_match.group("operand"))
    return expression == "0"


def _is_nonnegative_item_count_check(sqltext: object) -> bool:
    if not isinstance(sqltext, str):
        return False
    normalized = re.sub(r"\s+", "", sqltext.lower()).replace('"', "")
    comparison = _COMPARISON_RE.fullmatch(
        _strip_outer_parentheses(normalized)
    )
    if comparison is None:
        return False
    left = comparison.group("left")
    operator = comparison.group("operator")
    right = comparison.group("right")
    return (
        operator == ">="
        and _is_item_count_operand(left)
        and _is_zero_operand(right)
    ) or (
        operator == "<="
        and _is_zero_operand(left)
        and _is_item_count_operand(right)
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "provider_inventory_observations" not in inspector.get_table_names():
        op.create_table(
            "provider_inventory_observations",
            sa.Column("provider", sa.String(), primary_key=True),
            sa.Column("origin_code", sa.String(), primary_key=True),
            sa.Column("destination_code", sa.String(), primary_key=True),
            sa.Column("depart_date", sa.String(), primary_key=True),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.CheckConstraint(
                "item_count >= 0",
                name=_ITEM_COUNT_CHECK_NAME,
            ),
        )
        return

    check_constraints = inspector.get_check_constraints(
        "provider_inventory_observations"
    )
    named_check = next(
        (
            constraint
            for constraint in check_constraints
            if constraint.get("name") == _ITEM_COUNT_CHECK_NAME
        ),
        None,
    )
    if named_check is None:
        op.create_check_constraint(
            _ITEM_COUNT_CHECK_NAME,
            "provider_inventory_observations",
            "item_count >= 0",
        )
    elif not _is_nonnegative_item_count_check(named_check.get("sqltext")):
        raise RuntimeError(
            f"{_ITEM_COUNT_CHECK_NAME} has a mismatched definition; "
            "refusing to alter the existing table"
        )


def downgrade() -> None:
    raise RuntimeError(
        "20260718_provider_inventory is irreversible: provider inventory "
        "schema and data may predate Alembic"
    )
