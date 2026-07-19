from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.application.contracts.flight_provider import (
    PriceStatus,
    ProviderStatus,
    is_complete_https_url,
    normalize_currency_code,
)


ApiConfidence = Literal["high", "medium", "low"]
DataFreshness = Literal["fresh", "stale", "unknown"]


def _normalize_inventory_expiry(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("inventory expiry must be an ISO datetime")
    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("inventory expiry must be an ISO datetime") from exc
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry.astimezone(timezone.utc).isoformat()


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
    data_freshness: DataFreshness
    expires_at: Optional[str] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)

    @field_validator("url", mode="before")
    @classmethod
    def keep_only_complete_https_url(cls, value: object) -> str | None:
        return value if is_complete_https_url(value) else None

    @field_validator("expires_at", mode="before")
    @classmethod
    def normalize_expires_at(cls, value: object) -> str | None:
        return _normalize_inventory_expiry(value)


class DealCardDto(BaseModel):
    id: str
    system_id: str
    flight_no: str
    platform: str
    origin_city: str
    origin_code: str
    origin_airport_code: Optional[str] = None
    destination_city: str
    destination_code: str
    destination_airport_code: Optional[str] = None
    depart_date: str
    airline: str
    depart_time: str
    arrive_time: str
    duration_minutes: Optional[int] = None
    stops: int = 0
    price: Optional[int]
    lowest_price: Optional[int] = None
    base_price: Optional[int] = None
    tax: Optional[int] = None
    baggage_fee: Optional[int] = None
    has_baggage: Optional[bool] = None
    total_price: Optional[int] = None
    currency: str
    recommend_score: Optional[str] = None
    winning_price_id: Optional[str]
    prices: list[PriceItemDto] = Field(default_factory=list)
    original_price: Optional[int] = None
    discount_rate: Optional[float] = None
    cabin: Optional[str] = None
    signals: list[str] = Field(default_factory=list)
    confidence: ApiConfidence = "medium"
    verdict: str = ""
    booking_url: Optional[str] = None
    h5_fallback_url: Optional[str] = None
    data_freshness: DataFreshness
    inventory_expires_at: Optional[str] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)

    @field_validator("booking_url", "h5_fallback_url", mode="before")
    @classmethod
    def keep_only_complete_https_url(cls, value: object) -> str | None:
        return value if is_complete_https_url(value) else None

    @field_validator("inventory_expires_at", mode="before")
    @classmethod
    def normalize_inventory_expires_at(cls, value: object) -> str | None:
        return _normalize_inventory_expiry(value)

    @model_validator(mode="after")
    def validate_winning_price_contract(self) -> DealCardDto:
        if self.winning_price_id is None:
            if any(price.lowest is not False for price in self.prices):
                raise ValueError("every row must have lowest=false without a winner")
            if (
                self.platform
                or self.price is not None
                or self.lowest_price is not None
                or self.base_price is not None
                or self.total_price is not None
                or self.booking_url is not None
                or self.h5_fallback_url is not None
                or self.inventory_expires_at is not None
            ):
                raise ValueError("headline and booking require a winning row")
            return self

        matches = [
            price
            for price in self.prices
            if price.id == self.winning_price_id
        ]
        if len(matches) != 1:
            raise ValueError("winning_price_id must identify exactly one row")
        winner = matches[0]
        if any(
            price.lowest is not False
            for price in self.prices
            if price.id != self.winning_price_id
        ):
            raise ValueError("every nonwinning row must have lowest=false")
        fresh_winner = (
            winner.price_status is PriceStatus.priced
            and winner.provider_status is ProviderStatus.success
            and winner.data_freshness == "fresh"
        )
        stale_ctrip_winner = (
            winner.data_provider == "ctrip_snapshot"
            and winner.price_status is PriceStatus.stale
            and winner.provider_status is ProviderStatus.stale
            and winner.data_freshness == "stale"
            and winner.url is not None
        )
        if (
            winner.lowest is not True
            or winner.price is None
            or not (fresh_winner or stale_ctrip_winner)
        ):
            raise ValueError(
                "winning row must be fresh and successful or a stale Ctrip snapshot"
            )
        if (
            self.platform != winner.name
            or self.currency != winner.currency
            or self.price != winner.price
            or self.lowest_price != winner.price
            or self.total_price != winner.price
            or self.data_freshness != winner.data_freshness
            or self.inventory_expires_at != winner.expires_at
        ):
            raise ValueError("winning row must drive the headline")
        if (
            self.booking_url != winner.url
            or self.h5_fallback_url not in {None, winner.url}
        ):
            raise ValueError("winning row must drive the booking action")
        return self


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
