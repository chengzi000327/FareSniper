from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ApiConfidence = Literal["high", "medium", "low"]


class ApiMeta(BaseModel):
    generated_at: str
    source: Optional[str] = None
    request_id: Optional[str] = None
    result_count: Optional[int] = None
    fallback_mode: Optional[bool] = None
    clarify_count: Optional[int] = None


class PriceItemDto(BaseModel):
    name: str
    price: int
    lowest: Optional[bool] = None


class DealCardDto(BaseModel):
    id: str
    system_id: str
    platform: str
    origin_city: str
    origin_code: str
    destination_city: str
    destination_code: str
    depart_date: str
    airline: str
    depart_time: str
    arrive_time: str
    price: int
    tax: int = 0
    baggage_fee: int = 0
    has_baggage: bool = False
    recommend_score: str = ""
    prices: list[PriceItemDto] = Field(default_factory=list)
    original_price: Optional[int] = None
    discount_rate: Optional[float] = None
    cabin: Optional[str] = None
    signals: list[str] = Field(default_factory=list)
    confidence: ApiConfidence = "medium"
    verdict: str = ""
    booking_url: Optional[str] = None
    h5_fallback_url: Optional[str] = None


class RecommendationCardDto(BaseModel):
    id: str
    title: str
    reason: str
    query_hint: str
    tags: list[str] = Field(default_factory=list)
    preview_deal: Optional[DealCardDto] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
