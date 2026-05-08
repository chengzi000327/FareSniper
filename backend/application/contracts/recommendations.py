from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecCard(BaseModel):
    title: str
    reason: str
    preview_deal: dict[str, Any] | None = None


class RecommendationsResponseDto(BaseModel):
    personalized: bool = False
    cards: list[RecCard] = Field(default_factory=list)
