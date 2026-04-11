from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import FlightResultModel, RecommendationModel


class SearchRequest(BaseModel):
    user_id: str = "demo-user"
    message: str


class QueryModel(BaseModel):
    origin: str
    destination: str
    date_start: str
    date_end: str
    budget: Optional[int] = None
    raw_text: str
    normalized_text: str


class ComparisonModel(BaseModel):
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    avg_price: Optional[int] = None
    price_spread_pct: Optional[float] = None
    avg_90d: Optional[int] = None
    lower_than_avg: Optional[float] = None
    percentile: Optional[float] = None


class PreferenceMatchModel(BaseModel):
    match_score: float = 0.0
    within_budget: bool = False
    price_anchor: Optional[int] = None
    matched_destinations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: QueryModel
    flights: List[FlightResultModel] = Field(default_factory=list)
    comparison: ComparisonModel
    preference: PreferenceMatchModel
    recommendation: RecommendationModel
    metadata: Dict[str, Any] = Field(default_factory=dict)
