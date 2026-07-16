from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


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
    destination_city: str
    destination_code: str
    destination_airport_ids: list[str]
    depart_date: str
    currency: str = "CNY"
    is_mainland_domestic: bool


class FlightOffer(BaseModel):
    data_provider: str
    seller_name: str
    flight_no: str
    airline: str = ""
    origin_city: str
    origin_code: str
    destination_city: str
    destination_code: str
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
