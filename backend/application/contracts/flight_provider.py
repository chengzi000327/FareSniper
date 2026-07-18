from __future__ import annotations

from enum import Enum
from typing import Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


def is_complete_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.netloc and parsed.hostname)
    except ValueError:
        return False


def normalize_currency_code(value: object) -> object:
    if not isinstance(value, str):
        return value
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a three-letter code")
    return currency


class ProviderStatus(str, Enum):
    loading = "loading"
    queued = "queued"
    success = "success"
    empty = "empty"
    stale = "stale"
    timeout = "timeout"
    disabled = "disabled"
    error = "error"


class PriceStatus(str, Enum):
    priced = "priced"
    view_live_price = "view_live_price"
    stale = "stale"


class FlightQuery(BaseModel):
    origin_city: str
    origin_code: str
    origin_airport_ids: list[str]
    origin_airport_scope: str | None = None
    destination_city: str
    destination_code: str
    destination_airport_ids: list[str]
    destination_airport_scope: str | None = None
    depart_date: str
    currency: str = "CNY"
    is_mainland_domestic: bool

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)


class FlightOffer(BaseModel):
    data_provider: str
    seller_name: str
    flight_no: str
    airline: str = ""
    origin_city: str
    origin_code: str
    origin_airport_code: str | None = None
    destination_city: str
    destination_code: str
    destination_airport_code: str | None = None
    depart_date: str
    depart_time: str = ""
    arrive_time: str = ""
    duration_minutes: int | None = None
    stops: int = 0
    cabin: str | None = None
    currency: str = "CNY"
    base_price: int | None = None
    tax: int | None = None
    baggage_fee: int | None = None
    total_price: int | None = None
    has_baggage: bool | None = None
    price_status: PriceStatus = PriceStatus.priced
    booking_url: str | None = None
    fetched_at: str | None = None
    expires_at: str | None = None
    is_realtime: bool = True
    raw_reference: str | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return normalize_currency_code(value)

    @field_validator("booking_url", mode="before")
    @classmethod
    def keep_only_complete_https_booking_url(cls, value: object) -> str | None:
        return value if is_complete_https_url(value) else None

    @model_validator(mode="after")
    def validate_price_status(self) -> FlightOffer:
        is_live_price = self.price_status is PriceStatus.view_live_price
        has_https_booking_url = is_complete_https_url(self.booking_url)
        if self.total_price is None:
            if not is_live_price:
                raise ValueError("未知总价必须使用 view_live_price 状态")
            if not has_https_booking_url:
                raise ValueError("view_live_price 必须提供 HTTPS booking_url")
        elif is_live_price:
            raise ValueError("view_live_price 必须使用未知总价")
        return self


class ProviderResult(BaseModel):
    provider: str
    status: ProviderStatus
    offers: list[FlightOffer] = Field(default_factory=list)
    error_code: str | None = None
    message: str = ""
    latency_ms: int = 0
    cache_age_seconds: int | None = None


class FlightProvider(Protocol):
    name: str

    def supports(self, query: FlightQuery) -> bool: ...

    async def search(self, query: FlightQuery) -> ProviderResult: ...
