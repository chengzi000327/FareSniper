"""Dynamic intent registry contracts."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import BaseContract


class IntentDefinition(BaseContract):
    name: str
    description: str = ""
    required_slots: list[str] = Field(default_factory=list)
    optional_slots: list[str] = Field(default_factory=list)
    slot_schema: dict[str, Any] = Field(default_factory=dict)
    handler_name: str = ""
    keywords: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    is_active: bool = True
    priority: int = 100


class IntentMatch(BaseContract):
    intent_name: str
    confidence: float
    matched_by: str
    definition: IntentDefinition
