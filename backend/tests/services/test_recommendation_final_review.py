from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.application.contracts.recommendations import RecCard
import backend.application.services.recommendation_service as svc


def _preview_deal(
    *,
    currency: str = "CNY",
    expires_at: str = "2099-08-01T01:00:00+00:00",
) -> dict:
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
        "winning_price_id": "legacy-ctrip-cny",
        "prices": [
            {
                "id": "legacy-ctrip-cny",
                "name": "携程",
                "price": 580,
                "currency": currency,
                "lowest": True,
                "price_status": "priced",
                "provider_status": "success",
                "data_freshness": "fresh",
                "url": "https://flights.example.test/book?fixture=not-secret",
                "data_provider": "legacy",
                "expires_at": expires_at,
            }
        ],
        "signals": [],
        "booking_url": "https://flights.example.test/book?fixture=not-secret",
        "data_freshness": "fresh",
        "inventory_expires_at": expires_at,
    }


class StickyRedis:
    def __init__(self, raw: str | None = None):
        self.raw = raw
        self.ttls: list[int] = []

    async def get(self, key: str) -> str | None:
        return self.raw

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.ttls.append(ttl)
        self.raw = value


def _frozen_datetime(start: datetime):
    class FrozenDateTime(datetime):
        current = start

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current.replace(tzinfo=None)
            return cls.current.astimezone(tz)

    return FrozenDateTime


async def _identity_personalize(user_id: str, pool: list[RecCard]):
    return pool, False


def test_recommendation_pool_cache_version_excludes_pre_freshness_cards():
    assert svc.POOL_CACHE_KEY == "rec:pool:v3"


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
        "winning_price_id": "legacy-trip-usd",
        "data_freshness": "fresh",
        "prices": [
            {
                "id": "legacy-trip-usd",
                "platform": "Trip.com",
                "price": 80,
                "currency": "USD",
                "url": "https://booking.example.test/checkout",
                "price_status": "priced",
                "data_freshness": "fresh",
                "expires_at": "2099-08-01T01:00:00+00:00",
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
    assert card.preview_deal["winning_price_id"] == "legacy-trip-usd"
    assert card.preview_deal["prices"][0]["url"] == card.preview_deal["booking_url"]
    assert card.preview_deal["prices"][0]["expires_at"] == (
        "2099-08-01T01:00:00+00:00"
    )
    assert card.preview_deal["inventory_expires_at"] == (
        "2099-08-01T01:00:00+00:00"
    )


async def test_pool_cache_ttl_is_bounded_by_earliest_inventory_expiry(
    monkeypatch,
):
    now = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)
    FrozenDateTime = _frozen_datetime(now)
    expiry = now + timedelta(seconds=75)
    redis = StickyRedis()

    async def build_pool():
        return [
            RecCard(
                id="card-sha",
                title="北京→上海",
                reason="实时低价",
                preview_deal=_preview_deal(expires_at=expiry.isoformat()),
            ),
            RecCard(
                id="card-can",
                title="北京→广州",
                reason="稍后到期",
                preview_deal=_preview_deal(
                    expires_at=(now + timedelta(seconds=700)).isoformat()
                ),
            ),
        ]

    monkeypatch.setattr(svc, "datetime", FrozenDateTime)
    monkeypatch.setattr(svc, "_redis", lambda: redis)
    monkeypatch.setattr(svc, "_build_card_pool", build_pool)

    pool = await svc._get_card_pool()

    assert pool[0].preview_deal is not None
    assert redis.ttls == [75]
    envelope = json.loads(redis.raw or "null")
    assert envelope["version"] == svc.POOL_CACHE_ENVELOPE_VERSION
    assert envelope["inventory_expires_at"] == expiry.isoformat()
    assert envelope["cards"][0]["preview_deal"]["prices"][0][
        "expires_at"
    ] == expiry.isoformat()


async def test_cache_hit_after_inventory_expiry_downgrades_winner(
    monkeypatch,
):
    now = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)
    FrozenDateTime = _frozen_datetime(now)
    expiry = now + timedelta(seconds=60)
    redis = StickyRedis()
    build_calls = 0

    async def build_pool():
        nonlocal build_calls
        build_calls += 1
        return [
            RecCard(
                id="card-sha",
                title="北京→上海",
                reason="上海 实时低价，建议预订",
                discount_pct=20,
                preview_deal=_preview_deal(expires_at=expiry.isoformat()),
            )
        ]

    monkeypatch.setattr(svc, "datetime", FrozenDateTime)
    monkeypatch.setattr(svc, "_redis", lambda: redis)
    monkeypatch.setattr(svc, "_build_card_pool", build_pool)

    first = await svc._get_card_pool()
    assert first[0].preview_deal["winning_price_id"] == "legacy-ctrip-cny"

    FrozenDateTime.current = expiry
    second = await svc._get_card_pool()

    assert build_calls == 1
    card = second[0]
    assert card.preview_deal is not None
    preview = card.preview_deal
    assert preview["winning_price_id"] is None
    assert preview["platform"] == ""
    assert preview["price"] is None
    assert preview["lowest_price"] is None
    assert preview["total_price"] is None
    assert preview["booking_url"] is None
    assert preview["h5_fallback_url"] is None
    assert preview["data_freshness"] == "stale"
    assert preview["inventory_expires_at"] is None
    assert preview["prices"][0]["lowest"] is False
    assert preview["prices"][0]["price_status"] == "stale"
    assert preview["prices"][0]["provider_status"] == "stale"
    assert preview["prices"][0]["data_freshness"] == "stale"
    assert preview["prices"][0]["url"] is None
    assert card.discount_pct is None
    assert "持续监控" in card.reason


async def test_pool_build_revalidates_against_the_post_query_clock(monkeypatch):
    now = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)
    FrozenDateTime = _frozen_datetime(now)
    expiry = now + timedelta(seconds=1)
    redis = StickyRedis()

    async def build_pool():
        FrozenDateTime.current = expiry
        return [
            RecCard(
                id="card-sha",
                title="北京→上海",
                reason="实时低价",
                preview_deal=_preview_deal(expires_at=expiry.isoformat()),
            )
        ]

    monkeypatch.setattr(svc, "datetime", FrozenDateTime)
    monkeypatch.setattr(svc, "_redis", lambda: redis)
    monkeypatch.setattr(svc, "_build_card_pool", build_pool)

    cards = await svc._get_card_pool()

    assert cards[0].preview_deal is not None
    assert cards[0].preview_deal["winning_price_id"] is None
    assert cards[0].preview_deal["data_freshness"] == "stale"
    assert cards[0].preview_deal["booking_url"] is None


@pytest.mark.parametrize("expiry", [None, "not-an-instant"])
async def test_old_cache_payload_with_missing_or_invalid_expiry_downgrades(
    monkeypatch,
    expiry,
):
    preview = _preview_deal()
    if expiry is None:
        preview.pop("inventory_expires_at")
        preview["prices"][0].pop("expires_at")
    else:
        preview["inventory_expires_at"] = expiry
        preview["prices"][0]["expires_at"] = expiry
    old_payload = json.dumps(
        [
            RecCard(
                id="old-card",
                title="北京→上海",
                reason="旧缓存实时低价",
                discount_pct=15,
                preview_deal=preview,
            ).model_dump()
        ]
    )
    redis = StickyRedis(old_payload)

    async def should_not_rebuild():
        raise AssertionError("parseable old cache entries should downgrade in place")

    monkeypatch.setattr(svc, "_redis", lambda: redis)
    monkeypatch.setattr(svc, "_build_card_pool", should_not_rebuild)

    cards = await svc._get_card_pool()

    assert len(cards) == 1
    assert cards[0].preview_deal is not None
    assert cards[0].preview_deal["winning_price_id"] is None
    assert cards[0].preview_deal["booking_url"] is None
    assert cards[0].preview_deal["prices"][0]["url"] is None
    assert cards[0].preview_deal["prices"][0]["data_freshness"] == "unknown"
    assert cards[0].discount_pct is None


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_expired_or_unknown_inventory_is_reference_only(freshness):
    deal = {
        "flight_no": "MU5106",
        "depart_date": "2099-08-01",
        "airline": "东方航空",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "lowest_price": 500,
        "currency": "CNY",
        "winning_price_id": None,
        "data_freshness": freshness,
        "prices": [
            {
                "id": f"legacy-{freshness}",
                "platform": "携程",
                "price": 500,
                "currency": "CNY",
                "url": "https://booking.example.test/expired",
                "price_status": "priced",
                "data_freshness": freshness,
            }
        ],
    }

    card = svc._build_card("BJS", "SHA", deal, market_avg=None, sample_n=1)

    assert card.preview_deal is not None
    preview = card.preview_deal
    assert preview["winning_price_id"] is None
    assert preview["platform"] == ""
    assert preview["price"] is None
    assert preview["lowest_price"] is None
    assert preview["total_price"] is None
    assert preview["booking_url"] is None
    assert preview["data_freshness"] == freshness
    assert preview["prices"][0]["provider_status"] == "stale"
    assert preview["prices"][0]["data_freshness"] == freshness
    assert preview["prices"][0]["lowest"] is False
    assert "持续监控" in card.reason


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
                "winning_price_id": "global-usd",
                "data_freshness": "fresh",
                "prices": [
                    {
                        "id": "global-usd",
                        "platform": "Global",
                        "price": 80,
                        "currency": "USD",
                        "price_status": "priced",
                        "data_freshness": "fresh",
                        "expires_at": "2099-08-01T01:00:00+00:00",
                    }
                ],
            },
            {
                "flight_no": "CNY550",
                "airline": "东方航空",
                "dep_time": "09:00",
                "arr_time": "11:00",
                "lowest_price": 550,
                "currency": "CNY",
                "winning_price_id": "ctrip-cny",
                "data_freshness": "fresh",
                "prices": [
                    {
                        "id": "ctrip-cny",
                        "platform": "携程",
                        "price": 550,
                        "currency": "CNY",
                        "price_status": "priced",
                        "data_freshness": "fresh",
                        "expires_at": "2099-08-01T01:00:00+00:00",
                    }
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
