from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationInfo,
    field_validator,
)

from backend.application.contracts.collector import CollectorErrorCode
from backend.application.contracts.flight_provider import (
    FlightOffer,
    PriceStatus,
)
from backend.application.services.flight_dates import (
    validate_canonical_depart_date,
)


_CTRIP_BOOKING_HOST = "flights.ctrip.com"
_MAX_BOOKING_URL_LENGTH = 2048
_BOOKING_QUERY_ORDER = ("depdate", "cabin", "adult", "child", "infant")
_CABIN_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,16}\Z")
_AIRPORT_CODE_PATTERN = re.compile(r"[A-Z]{3}\Z")
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_CTRIP_ROUTE_PATH_PATTERN = re.compile(
    r"/online/list/oneway-([a-z]{3})-([a-z]{3})\Z"
)
_RFC3339_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def normalize_ctrip_booking_url(
    value: str,
    *,
    depart_date: str | None,
    origin_codes: tuple[str | None, ...],
    destination_codes: tuple[str | None, ...],
) -> str:
    if len(value) > _MAX_BOOKING_URL_LENGTH:
        raise ValueError("invalid booking URL")
    _reject_invalid_percent_encoding(value)
    if _has_control_characters(value) or "#" in value:
        raise ValueError("invalid booking URL")

    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid booking URL") from exc
    if (
        parsed.scheme.casefold() != "https"
        or parsed.netloc.casefold() != _CTRIP_BOOKING_HOST
        or parsed.hostname != _CTRIP_BOOKING_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
    ):
        raise ValueError("invalid booking URL")

    route_match = _CTRIP_ROUTE_PATH_PATTERN.fullmatch(parsed.path)
    if route_match is None:
        raise ValueError("invalid booking URL")
    allowed_origins = _normalized_route_codes(origin_codes)
    allowed_destinations = _normalized_route_codes(destination_codes)
    if (
        route_match.group(1).upper() not in allowed_origins
        or route_match.group(2).upper() not in allowed_destinations
    ):
        raise ValueError("invalid booking URL")

    query = _normalize_booking_query(
        parsed.query,
        depart_date=depart_date,
    )
    return urlunsplit(
        ("https", _CTRIP_BOOKING_HOST, parsed.path, query, "")
    )


def _normalized_route_codes(values: tuple[str | None, ...]) -> set[str]:
    normalized = {
        value.upper()
        for value in values
        if isinstance(value, str) and _AIRPORT_CODE_PATTERN.fullmatch(value)
    }
    if not normalized:
        raise ValueError("invalid booking URL")
    return normalized


def _reject_invalid_percent_encoding(value: str) -> None:
    for index, character in enumerate(value):
        if character != "%":
            continue
        escape = value[index + 1 : index + 3]
        if len(escape) != 2 or any(char not in _HEX_DIGITS for char in escape):
            raise ValueError("invalid booking URL")


def _has_control_characters(value: str) -> bool:
    try:
        decoded = unquote(value, encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid booking URL") from exc
    return any(
        unicodedata.category(character) == "Cc"
        for character in value + decoded
    )


def _normalize_booking_query(
    query: str,
    *,
    depart_date: str | None,
) -> str:
    if not query:
        raise ValueError("invalid booking URL")
    try:
        pairs = parse_qsl(
            query,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            separator="&",
        )
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid booking URL") from exc

    normalized: dict[str, str] = {}
    for key, value in pairs:
        if key not in _BOOKING_QUERY_ORDER or key in normalized:
            raise ValueError("invalid booking URL")
        if key == "depdate":
            normalized[key] = _validate_booking_date(value, depart_date)
        elif key == "cabin":
            if _CABIN_PATTERN.fullmatch(value) is None:
                raise ValueError("invalid booking URL")
            normalized[key] = value
        else:
            minimum = 1 if key == "adult" else 0
            normalized[key] = _validate_passenger_count(value, minimum)

    if "depdate" not in normalized:
        raise ValueError("invalid booking URL")

    return urlencode(
        [(key, normalized[key]) for key in _BOOKING_QUERY_ORDER if key in normalized]
    )


def _validate_booking_date(value: str, expected: str | None) -> str:
    if _DATE_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid booking URL")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid booking URL") from exc
    if expected is not None and value != expected:
        raise ValueError("invalid booking URL")
    return value


def _validate_passenger_count(value: str, minimum: int) -> str:
    if not value.isascii() or not value.isdecimal():
        raise ValueError("invalid booking URL")
    count = int(value)
    if not minimum <= count <= 9 or str(count) != value:
        raise ValueError("invalid booking URL")
    return value


class CollectorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimRequest(CollectorRequest):
    node_id: str = Field(min_length=1, max_length=128)


class CollectorJobResponse(BaseModel):
    job_id: str
    origin_code: str
    origin_airport_code: str | None = None
    destination_code: str
    destination_airport_code: str | None = None
    depart_date: str
    source: str
    priority: int
    attempts: int
    lease_expires_at: datetime


class ClaimResponse(BaseModel):
    job: CollectorJobResponse | None


class HeartbeatRequest(CollectorRequest):
    node_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)


class CollectorStatusResponse(BaseModel):
    collector_online: bool
    last_heartbeat_at: datetime | None = None
    last_success_at: datetime | None = None
    job_status: Literal[
        "missing", "pending", "leased", "retry", "completed", "failed"
    ]
    job_attempts: int = Field(ge=0)
    job_updated_at: datetime | None = None
    snapshot_observed_at: datetime | None = None


class CollectorOffer(CollectorRequest):
    data_provider: Literal["ctrip_snapshot"]
    seller_name: Literal["携程"]
    flight_no: str = Field(min_length=1, max_length=64)
    airline: str = Field(default="", max_length=128)
    origin_city: str = Field(min_length=1, max_length=128)
    origin_code: str = Field(min_length=1, max_length=16)
    origin_airport_code: str = Field(pattern=_AIRPORT_CODE_PATTERN)
    destination_city: str = Field(min_length=1, max_length=128)
    destination_code: str = Field(min_length=1, max_length=16)
    destination_airport_code: str = Field(pattern=_AIRPORT_CODE_PATTERN)
    depart_date: str
    depart_time: str = Field(default="", max_length=16)
    arrive_time: str = Field(default="", max_length=16)
    duration_minutes: Annotated[StrictInt, Field(ge=0)] | None = None
    stops: Annotated[StrictInt, Field(ge=0)] = 0
    cabin: str | None = Field(default=None, max_length=32)
    currency: Literal["CNY"]
    base_price: Annotated[StrictInt, Field(gt=0)] | None = None
    tax: Annotated[StrictInt, Field(ge=0)] | None = None
    tax_source: Literal["provider", "regulatory_estimate"] | None = None
    baggage_fee: Annotated[StrictInt, Field(ge=0)] | None = None
    baggage_allowance: str | None = Field(default=None, max_length=128)
    has_baggage: bool | None = None
    display_price: Annotated[StrictInt, Field(gt=0)]
    booking_url: str = Field(max_length=_MAX_BOOKING_URL_LENGTH)

    @field_validator("depart_date")
    @classmethod
    def validate_depart_date(cls, value: str) -> str:
        return validate_canonical_depart_date(value)

    @field_validator("booking_url")
    @classmethod
    def validate_ctrip_booking_url(
        cls,
        value: str,
        info: ValidationInfo,
    ) -> str:
        return normalize_ctrip_booking_url(
            value,
            depart_date=info.data.get("depart_date"),
            origin_codes=(
                info.data.get("origin_code"),
                info.data.get("origin_airport_code"),
            ),
            destination_codes=(
                info.data.get("destination_code"),
                info.data.get("destination_airport_code"),
            ),
        )

    def to_internal_offer(self) -> FlightOffer:
        return FlightOffer(
            data_provider="ctrip",
            seller_name="携程",
            flight_no=self.flight_no,
            airline=self.airline,
            origin_city=self.origin_city,
            origin_code=self.origin_code,
            origin_airport_code=self.origin_airport_code,
            destination_city=self.destination_city,
            destination_code=self.destination_code,
            destination_airport_code=self.destination_airport_code,
            depart_date=self.depart_date,
            depart_time=self.depart_time,
            arrive_time=self.arrive_time,
            duration_minutes=self.duration_minutes,
            stops=self.stops,
            cabin=self.cabin,
            currency="CNY",
            base_price=self.base_price,
            tax=self.tax,
            tax_source=self.tax_source,
            baggage_fee=self.baggage_fee,
            baggage_allowance=self.baggage_allowance,
            total_price=self.display_price,
            has_baggage=self.has_baggage,
            price_status=PriceStatus.priced,
            booking_url=self.booking_url,
            raw_reference=None,
        )


class CompleteRequest(CollectorRequest):
    node_id: str = Field(min_length=1, max_length=128)
    offers: list[CollectorOffer] = Field(min_length=1, max_length=500)


class FailRequest(CollectorRequest):
    node_id: str = Field(min_length=1, max_length=128)
    error_code: CollectorErrorCode
    retry_at: datetime

    @field_validator("retry_at", mode="before")
    @classmethod
    def parse_rfc3339_retry_at(cls, value: object) -> datetime:
        if not isinstance(value, str) or _RFC3339_PATTERN.fullmatch(value) is None:
            raise ValueError("retry_at must be an RFC3339 timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("retry_at must be an RFC3339 timestamp") from exc
        if parsed.utcoffset() is None:
            raise ValueError("retry_at must be timezone-aware")
        return parsed
