from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import RecommendationCardModel


class PreferenceItemModel(BaseModel):
    field: str
    value: Any
    source: str = "manual"
    updated_at: str


class MemoryResponse(BaseModel):
    user_id: str
    preferences: List[PreferenceItemModel] = Field(default_factory=list)
    query_history: List[Dict[str, Any]] = Field(default_factory=list)
    click_history: List[Dict[str, Any]] = Field(default_factory=list)


class MemoryPatchRequest(BaseModel):
    user_id: str
    field: str
    value: Any
    source: str = "manual"


class RecommendationsResponse(BaseModel):
    user_id: str
    cards: List[RecommendationCardModel] = Field(default_factory=list)
    source: str = "mock"
    generated_at: str
