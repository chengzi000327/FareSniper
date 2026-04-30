"""Flight search result contracts."""

from __future__ import annotations

from pydantic import Field

from .base import BaseContract


class PlatformPrice(BaseContract):
    platform: str
    price: int
    url: str = ""
    lowest: bool = False


class FlightCandidate(BaseContract):
    flight_no: str
    airline: str
    depart_time: str
    arrive_time: str
    duration: str
    stops: int = 0
    depart_date: str
    origin_city: str = ""
    origin_code: str = ""
    destination_city: str = ""
    destination_code: str = ""
    prices: list[PlatformPrice] = Field(default_factory=list)
    price: int = 0
    lowest_price: int = 0
    history_avg_90d: float | None = None
    history_low_90d: float | None = None
    is_holiday: bool = False
    signals: list[str] = Field(default_factory=list)
    verdict: str = ""
    recommend_score: str = "0.0"
    confidence: str = "low"
    has_baggage: bool = True
    tax: int = 0
    baggage_fee: int = 0
    booking_url: str = ""
    h5_fallback_url: str = ""


class FlightSearchResult(BaseContract):
    candidates: list[FlightCandidate] = Field(default_factory=list)
    source: str = "mock"
    query_origin: str = ""
    query_destination: str = ""
    query_date: str = ""
