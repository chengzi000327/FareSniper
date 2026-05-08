"""Preference matching contracts."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field

from pydantic import Field

from .base import BaseContract


@dataclass
class Memory:
    budget_ceiling: int | None = None
    preferred_airlines: list[str] = dc_field(default_factory=list)
    constraints: list[str] = dc_field(default_factory=list)


class PreferenceMatchItem(BaseContract):
    flight_no: str
    matched: bool = False
    boost: bool = False
    reasons: list[str] = Field(default_factory=list)


class PreferenceMatchResult(BaseContract):
    items: list[PreferenceMatchItem] = Field(default_factory=list)
