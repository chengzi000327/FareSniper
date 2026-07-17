from __future__ import annotations

from datetime import date


INVALID_DEPART_DATE_MESSAGE = "depart_date must be a valid YYYY-MM-DD date"


def is_canonical_depart_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def validate_canonical_depart_date(value: str) -> str:
    if not is_canonical_depart_date(value):
        raise ValueError(INVALID_DEPART_DATE_MESSAGE)
    return value
