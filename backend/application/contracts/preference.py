"""Preference matching contracts."""

from __future__ import annotations

from pydantic import Field

from .base import BaseContract


class PreferenceMatchItem(BaseContract):
    flight_no: str
    matched: bool = False
    boost: bool = False
    reasons: list[str] = Field(default_factory=list)


class PreferenceMatchResult(BaseContract):
    items: list[PreferenceMatchItem] = Field(default_factory=list)
