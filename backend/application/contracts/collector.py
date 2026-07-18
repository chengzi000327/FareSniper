from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.application.contracts.flight_provider import FlightOffer


class CollectorErrorCode(str, Enum):
    dependency_error = "dependency_error"
    login_required = "login_required"
    captcha_required = "captcha_required"
    timeout = "timeout"
    empty = "empty"
    parse_error = "parse_error"


@dataclass(frozen=True)
class CollectorSearchResult:
    offers: list[FlightOffer] = field(default_factory=list)
    error_code: CollectorErrorCode | None = None
