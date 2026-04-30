"""Decision and frontend response contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from .base import BaseContract


class RecommendedAction(str, Enum):
    buy_now = "buy_now"
    watch = "watch"
    skip = "skip"


class DecisionFactor(BaseContract):
    factor_type: str
    summary: str
    weight: float = 1.0


class DecisionResult(BaseContract):
    action: RecommendedAction
    confidence: str = "low"
    text: str
    signals: list[str] = Field(default_factory=list)
    decision_factors: list[DecisionFactor] = Field(default_factory=list)
    branch_reason: str = ""


class FrontendResponse(BaseContract):
    user_id: str
    query: dict[str, Any] | None = None
    deals: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
