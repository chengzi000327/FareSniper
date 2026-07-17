from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.application.contracts.flight_provider import (
    PriceStatus,
    ProviderStatus,
    is_complete_https_url,
    normalize_currency_code,
)


ApiConfidence = Literal["high", "medium", "low"]


class ApiMeta(BaseModel):
    generated_at: str
    source: Optional[str] = None
    request_id: Optional[str] = None
    result_count: Optional[int] = None
    fallback_mode: Optional[bool] = None
    clarify_count: Optional[int] = None


class PriceItemDto(BaseModel):
    id: str
    name: str
    price: Optional[int]
    currency: str
    lowest: Optional[bool] = None
    price_status: Optional[PriceStatus] = None
    provider_status: ProviderStatus
    url: Optional[str] = None
    data_provider: str = ""

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)

    @field_validator("url", mode="before")
    @classmethod
    def keep_only_complete_https_url(cls, value: object) -> str | None:
        return value if is_complete_https_url(value) else None


class DealCardDto(BaseModel):
    id: str
    system_id: str
    flight_no: str
    platform: str
    origin_city: str
    origin_code: str
    destination_city: str
    destination_code: str
    depart_date: str
    airline: str
    depart_time: str
    arrive_time: str
    duration_minutes: Optional[int] = None
    stops: int = 0
    price: Optional[int]
    lowest_price: Optional[int] = None
    tax: Optional[int] = None
    baggage_fee: Optional[int] = None
    has_baggage: Optional[bool] = None
    total_price: Optional[int] = None
    currency: str
    recommend_score: Optional[str] = None
    prices: list[PriceItemDto] = Field(default_factory=list)
    original_price: Optional[int] = None
    discount_rate: Optional[float] = None
    cabin: Optional[str] = None
    signals: list[str] = Field(default_factory=list)
    confidence: ApiConfidence = "medium"
    verdict: str = ""
    booking_url: Optional[str] = None
    h5_fallback_url: Optional[str] = None
    data_freshness: Optional[str] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)

    @field_validator("booking_url", "h5_fallback_url", mode="before")
    @classmethod
    def keep_only_complete_https_url(cls, value: object) -> str | None:
        return value if is_complete_https_url(value) else None


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
