from __future__ import annotations

from backend.application.contracts.recommendations import RecCard
import backend.application.services.recommendation_service as svc


def _preview_deal(*, currency: str = "CNY") -> dict:
    return {
        "id": "valid-deal",
        "system_id": "MU5106-2099-08-01",
        "flight_no": "MU5106",
        "platform": "携程",
        "origin_city": "北京",
        "origin_code": "BJS",
        "destination_city": "上海",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "airline": "东方航空",
        "depart_time": "08:00",
        "arrive_time": "10:00",
        "duration_minutes": 120,
        "stops": 0,
        "price": 580,
        "lowest_price": 580,
        "tax": None,
        "baggage_fee": None,
        "has_baggage": None,
        "total_price": 580,
        "currency": currency,
        "recommend_score": None,
        "prices": [
            {
                "id": "legacy-ctrip-cny",
                "name": "携程",
                "price": 580,
                "currency": currency,
                "lowest": True,
                "price_status": "priced",
                "provider_status": "success",
                "url": "https://flights.example.test/book?fixture=not-secret",
                "data_provider": "legacy",
            }
        ],
        "signals": [],
        "booking_url": "https://flights.example.test/book?fixture=not-secret",
    }


async def _identity_personalize(user_id: str, pool: list[RecCard]):
    return pool, False


async def test_server_pagination_skips_empty_cards_before_slicing(monkeypatch):
    pool = [
        RecCard(title=f"empty-{index}", reason="empty", preview_deal=None)
        for index in range(6)
    ] + [
        RecCard(title="valid-later-page", reason="valid", preview_deal=_preview_deal())
    ]

    async def fake_pool():
        return pool

    monkeypatch.setattr(svc, "_get_card_pool", fake_pool)
    monkeypatch.setattr(svc, "_personalize", _identity_personalize)

    response = await svc.build_recommendations("u1", limit=6, offset=0)

    assert [card.title for card in response.cards] == ["valid-later-page"]
    assert response.has_more is False
    assert response.next_offset == 1


async def test_historical_only_inventory_never_becomes_a_preview_link(monkeypatch):
    latest_calls = 0

    async def no_upcoming(**kwargs):
        return []

    async def historical_latest(**kwargs):
        nonlocal latest_calls
        latest_calls += 1
        return [
            {
                "flight_no": "PAST1",
                "depart_date": "2020-01-01",
                "lowest_price": 280,
                "prices": [{"platform": "携程", "price": 280}],
            }
        ]

    monkeypatch.setattr(svc, "HOT_ROUTES", [("BJS", "SHA")])
    monkeypatch.setattr(svc, "read_deals", no_upcoming)
    monkeypatch.setattr(
        svc, "read_deals_latest", historical_latest, raising=False
    )

    cards = await svc._build_card_pool()

    assert cards[0].preview_deal is None
    assert latest_calls == 0


def test_recommendation_preview_keeps_currency_without_fabricated_score_or_fees():
    deal = {
        "flight_no": "SQ833",
        "depart_date": "2099-08-01",
        "airline": "Singapore Airlines",
        "dep_time": "08:00",
        "arr_time": "14:00",
        "lowest_price": 80,
        "currency": "USD",
        "prices": [
            {
                "platform": "Trip.com",
                "price": 80,
                "currency": "USD",
                "url": "https://booking.example.test/checkout",
            }
        ],
    }

    card = svc._build_card("BJS", "SIN", deal, market_avg=None, sample_n=1)

    assert card.preview_deal is not None
    assert card.preview_deal["currency"] == "USD"
    assert card.preview_deal["recommend_score"] is None
    assert card.preview_deal["tax"] is None
    assert card.preview_deal["baggage_fee"] is None
    assert card.preview_deal["has_baggage"] is None


async def test_card_pool_selects_and_compares_one_currency_per_route(monkeypatch):
    async def mixed_currency_batch(**kwargs):
        return [
            {
                "flight_no": "USD80",
                "airline": "Global Air",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "lowest_price": 80,
                "currency": "USD",
                "prices": [
                    {"platform": "Global", "price": 80, "currency": "USD"}
                ],
            },
            {
                "flight_no": "CNY550",
                "airline": "东方航空",
                "dep_time": "09:00",
                "arr_time": "11:00",
                "lowest_price": 550,
                "currency": "CNY",
                "prices": [
                    {"platform": "携程", "price": 550, "currency": "CNY"}
                ],
            },
        ]

    monkeypatch.setattr(svc, "HOT_ROUTES", [("BJS", "SHA")])
    monkeypatch.setattr(svc, "read_deals", mixed_currency_batch)

    cards = await svc._build_card_pool()

    preview = cards[0].preview_deal
    assert preview is not None
    assert preview["flight_no"] == "CNY550"
    assert preview["currency"] == "CNY"
    assert preview["price"] == 550
