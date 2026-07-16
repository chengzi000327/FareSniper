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
    price: Optional[int]
    lowest: Optional[bool] = None
    status: str = "priced"
    url: Optional[str] = None
    data_provider: str = ""


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
    price: Optional[int]
    tax: Optional[int] = None
    baggage_fee: Optional[int] = None
    has_baggage: Optional[bool] = None
    total_price: Optional[int] = None
    currency: str = "CNY"
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
    graph_compiled: bool = False
    redis_ok: bool = False
    postgres_ok: bool = False
    scheduler_ok: bool = False
    langsmith_ok: bool = False
