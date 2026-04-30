"""Intent parsing output contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from .base import BaseContract


class IntentConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class LocationRef(BaseContract):
    city: str | None = None
    iata_code: str | None = None
    confidence: float = 1.0


class DateWindow(BaseContract):
    start_date: str | None = None
    end_date: str | None = None
    is_flexible: bool = False


class IntentConstraintType(str, Enum):
    avoid_red_eye = "avoid_redeye"
    direct_only = "direct_only"
    prefer_morning = "prefer_morning"


class IntentConstraint(BaseContract):
    type: IntentConstraintType
    value: bool = True


class NormalizedIntent(BaseContract):
    origin: LocationRef | None = None
    destination: LocationRef | None = None
    date_window: DateWindow | None = None
    budget_cny: int | None = None
    constraints: list[IntentConstraint] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    intent_confidence: IntentConfidence = IntentConfidence.medium
    raw_text: str = ""
    parse_failed: bool = False


def is_intent_complete(intent: NormalizedIntent) -> bool:
    """Return whether the required search slots are present."""
    return (
        intent.origin is not None
        and intent.origin.city is not None
        and intent.destination is not None
        and intent.destination.city is not None
        and intent.date_window is not None
        and intent.date_window.start_date is not None
    )
