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
    r"^\s*(?P<left>.+?)\s*(?P<operator>>=|<=)\s*(?P<right>.+?)\s*$",
    re.DOTALL,
)
_ZERO_CAST_RE = re.compile(
    r"^(?P<operand>.+?)\s*::\s*"
    r"(?:smallint|integer|bigint|numeric"
    r"(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _outer_parentheses_wrap_expression(expression: str) -> bool:
    if not expression.startswith("(") or not expression.endswith(")"):
        return False
    depth = 0
    in_quotes = False
    index = 0
    while index < len(expression):
        character = expression[index]
        if character == '"':
            if (
                in_quotes
                and index + 1 < len(expression)
                and expression[index + 1] == '"'
            ):
                index += 2
                continue
            in_quotes = not in_quotes
        elif not in_quotes:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth < 0:
                    return False
                if depth == 0:
                    return index == len(expression) - 1
        index += 1
    return False


def _strip_outer_parentheses(expression: str) -> str:
    expression = expression.strip()
    while _outer_parentheses_wrap_expression(expression):
        expression = expression[1:-1].strip()
    return expression


def _is_item_count_operand(expression: str) -> bool:
    expression = _strip_outer_parentheses(expression)
    if expression == '"item_count"':
        return True
    return re.fullmatch(r"item_count", expression, re.IGNORECASE) is not None


def _is_zero_operand(expression: str) -> bool:
    expression = _strip_outer_parentheses(expression)
    while cast_match := _ZERO_CAST_RE.fullmatch(expression):
        expression = _strip_outer_parentheses(cast_match.group("operand"))
    return expression == "0"


def _is_nonnegative_item_count_check(sqltext: object) -> bool:
    if not isinstance(sqltext, str):
        return False
    comparison = _COMPARISON_RE.fullmatch(
        _strip_outer_parentheses(sqltext)
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
