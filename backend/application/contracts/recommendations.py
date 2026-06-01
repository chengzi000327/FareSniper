from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecCard(BaseModel):
    id: str = ""
    title: str
    reason: str
    tags: list[str] = Field(default_factory=list)
    discount_pct: int | None = None      # 低于均价的百分比（正数=便宜）
    preview_deal: dict[str, Any] | None = None


class RecommendationsResponseDto(BaseModel):
    personalized: bool = False
    cards: list[RecCard] = Field(default_factory=list)
