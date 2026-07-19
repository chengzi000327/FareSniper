from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import ApiConfidence, ApiMeta, DealCardDto

ApiRecommendationAction = Literal["buy_now", "watch", "skip"]


class SearchRequest(BaseModel):
    user_id: str = "demo-user"
    session_id: Optional[str] = None
    message: str


class SearchQueryDto(BaseModel):
    raw_text: str = ""
    normalized_text: str = ""
    origin_city: str
    origin_code: str
    origin_airport_ids: list[str] = Field(default_factory=list)
    origin_airport_scope: Optional[str] = None
    destination_city: str
    destination_code: str
    destination_airport_ids: list[str] = Field(default_factory=list)
    destination_airport_scope: Optional[str] = None
    date_start: str
    date_end: str
    budget: Optional[int] = None


class SearchAnalysisDto(BaseModel):
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    avg_price: Optional[int] = None
    avg_90d: Optional[int] = None
    lower_than_avg: Optional[float] = None
    price_spread_pct: Optional[float] = None
    match_score: float = 0.0
    within_budget: bool = False
    matched_preferences: list[str] = Field(default_factory=list)


class SearchRecommendationDto(BaseModel):
    action: ApiRecommendationAction = "watch"
    text: str
    confidence: ApiConfidence = "medium"
    signals: list[str] = Field(default_factory=list)


class SearchResponseDto(BaseModel):
    user_id: str
    query: Optional[SearchQueryDto] = None
    deals: list[DealCardDto] = Field(default_factory=list)
    analysis: SearchAnalysisDto
    recommendation: SearchRecommendationDto
    meta: ApiMeta


SearchResponse = SearchResponseDto
