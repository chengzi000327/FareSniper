from __future__ import annotations

import json

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    ProviderResult,
    ProviderStatus,
)
from backend.application.services.flight_offer_normalizer import offers_to_deals
from backend.application.services.search_events import SearchEventEmitter
from backend.schemas.common import DealCardDto


def _fixture_query() -> FlightQuery:
    return FlightQuery(
        origin_city="北京",
        origin_code="BJS",
        origin_airport_ids=["PEK", "PKX"],
        destination_city="上海",
        destination_code="SHA",
        destination_airport_ids=["SHA", "PVG"],
        depart_date="2099-08-01",
        currency="CNY",
        is_mainland_domestic=True,
    )


def _fixture_offer(
    *,
    provider: str,
    seller: str,
    price: int,
    currency: str,
    url: str,
    is_realtime: bool = True,
    expires_at: str | None = None,
) -> FlightOffer:
    return FlightOffer(
        data_provider=provider,
        seller_name=seller,
        flight_no="FS100",
        airline="Fixture Air",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        depart_time="08:00",
        arrive_time="10:00",
        currency=currency,
        total_price=price,
        booking_url=url,
        expires_at=expires_at,
        is_realtime=is_realtime,
    )


def _fixture_deal() -> dict:
    query = _fixture_query()
    results = {
        "ctrip": ProviderResult(
            provider="ctrip",
            status=ProviderStatus.success,
            offers=[
                _fixture_offer(
                    provider="ctrip_snapshot",
                    seller="携程",
                    price=500,
                    currency="CNY",
                    url="https://ctrip.example.test/reference",
                    is_realtime=False,
                    expires_at="2099-08-01T01:00:00+00:00",
                )
            ],
        ),
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _fixture_offer(
                    provider="flyai",
                    seller="飞猪",
                    price=580,
                    currency="CNY",
                    url=(
                        "https://book.example.test/flight"
                        "?offer=fixture-token-not-secret&channel=web"
                    ),
                    expires_at="2099-08-01T00:45:00+00:00",
                )
            ],
        ),
        "serpapi": ProviderResult(
            provider="serpapi",
            status=ProviderStatus.success,
            offers=[
                _fixture_offer(
                    provider="serpapi_google_flights",
                    seller="Global Seller",
                    price=80,
                    currency="USD",
                    url=(
                        "https://global.example.test/book"
                        "?offer=fixture-usd-token-not-secret"
                    ),
                )
            ],
        ),
    }
    deal = offers_to_deals(query, results)[0]
    return DealCardDto.model_validate(deal).model_dump(mode="json")


def build_fixture_events() -> list[dict]:
    events: list[dict] = []
    emitter = SearchEventEmitter("fixture-search", events.append)
    deal = _fixture_deal()
    emitter.emit("started", {"providers": ["fixture"]})
    emitter.emit(
        "provider_status", {"provider": "fixture", "status": "loading"}
    )
    result = {
        "deals": [deal],
        "source": "multi_provider",
        "provider_statuses": {"fixture": "success"},
        "errors": {},
    }
    emitter.emit("results", result)
    emitter.emit(
        "complete",
        {
            "response": {
                "user_id": "fixture-user",
                "session_id": "fixture-session",
                "query": None,
                "deals": [deal],
                "analysis": {},
                "recommendation": {"text": "fixture"},
                "meta": {"source": "multi_provider"},
            }
        },
    )
    return events


if __name__ == "__main__":
    for event in build_fixture_events():
        print(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
