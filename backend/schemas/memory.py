from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field

from backend.schemas.common import ApiMeta, RecommendationCardDto

MemoryValue = Union[str, int, list[str]]


class MemoryItemDto(BaseModel):
    id: str
    field: str
    label: str
    value: MemoryValue
    value_display: str
    source: Literal["manual", "auto"] = "manual"
    updated_at: str


class QueryHistoryItemDto(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ClickHistoryItemDto(BaseModel):
    flight_info: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class MemoryResponseDto(BaseModel):
    user_id: str
    memories: list[MemoryItemDto] = Field(default_factory=list)
    query_history: list[QueryHistoryItemDto] = Field(default_factory=list)
    click_history: list[ClickHistoryItemDto] = Field(default_factory=list)
    meta: ApiMeta


class MemoryPatchRequest(BaseModel):
    user_id: str
    field: str
    value: MemoryValue
    source: Literal["manual", "auto"] = "manual"


class RecommendationsResponseDto(BaseModel):
    user_id: str
    cards: list[RecommendationCardDto] = Field(default_factory=list)
    meta: ApiMeta


# 向后兼容别名（Step 8 删除）
MemoryResponse = MemoryResponseDto
RecommendationsResponse = RecommendationsResponseDto
