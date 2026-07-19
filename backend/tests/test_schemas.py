"""
Step 5 Schema 测试 — 对齐 frontend/types/api.ts
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


# ── DealCardDto ──────────────────────────────────────────────────────────────

def _deal_payload(**overrides) -> dict:
    base = {
        "id": "deal-001",
        "system_id": "SYS.042",
        "flight_no": "CA901",
        "platform": "ctrip",
        "origin_city": "北京",
        "origin_code": "PEK",
        "destination_city": "东京",
        "destination_code": "NRT",
        "depart_date": "2026-05-01",
        "airline": "国航",
        "depart_time": "08:00",
        "arrive_time": "13:30",
        "price": 2580,
        "lowest_price": 2580,
        "total_price": 2580,
        "currency": "CNY",
        "winning_price_id": "legacy-ctrip-cny",
        "data_freshness": "fresh",
        "prices": [
            {
                "id": "legacy-ctrip-cny",
                "name": "ctrip",
                "price": 2580,
                "currency": "CNY",
                "lowest": True,
                "price_status": "priced",
                "provider_status": "success",
                "url": None,
                "data_provider": "legacy",
                "data_freshness": "fresh",
            }
        ],
        "original_price": None,
        "discount_rate": None,
        "cabin": "economy",
        "signals": ["低于均价15%"],
        "confidence": "high",
        "verdict": "建议购买",
        "booking_url": None,
    }
    return {**base, **overrides}


def test_deal_card_all_fields():
    """DealCardDto 包含全部字段且能正常 validate。"""
    from backend.schemas.common import DealCardDto

    dto = DealCardDto.model_validate(_deal_payload())
    assert dto.id == "deal-001"
    assert dto.system_id == "SYS.042"
    assert dto.origin_city == "北京"
    assert dto.confidence == "high"
    assert dto.signals == ["低于均价15%"]
    assert dto.booking_url is None


def test_deal_card_confidence_values():
    """confidence 只接受 high / medium / low。"""
    from backend.schemas.common import DealCardDto

    for val in ("high", "medium", "low"):
        dto = DealCardDto.model_validate(_deal_payload(confidence=val))
        assert dto.confidence == val


def test_deal_card_missing_required_field():
    """缺少必填字段 price 应抛出 ValidationError。"""
    from backend.schemas.common import DealCardDto

    payload = _deal_payload()
    del payload["price"]
    with pytest.raises(ValidationError):
        DealCardDto.model_validate(payload)


def test_deal_card_requires_currency_instead_of_fabricating_one():
    from backend.schemas.common import DealCardDto

    payload = _deal_payload()
    del payload["currency"]

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(payload)


def test_deal_card_rejects_a_winner_that_disagrees_with_the_headline():
    from backend.schemas.common import DealCardDto

    payload = _deal_payload(
        platform="other seller",
        booking_url="https://other.example.test/book",
    )

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(payload)


def test_deal_card_accepts_stale_ctrip_winner_with_matching_link():
    from backend.schemas.common import DealCardDto

    row = {
        **_deal_payload()["prices"][0],
        "id": "ctrip-stale-cny",
        "name": "携程",
        "price": 500,
        "lowest": True,
        "price_status": "stale",
        "provider_status": "stale",
        "url": "https://ctrip.example.test/book",
        "data_provider": "ctrip_snapshot",
        "data_freshness": "stale",
        "expires_at": "2000-01-01T00:00:00+00:00",
    }
    dto = DealCardDto.model_validate(
        _deal_payload(
            platform="携程",
            price=500,
            lowest_price=500,
            total_price=500,
            winning_price_id="ctrip-stale-cny",
            data_freshness="stale",
            prices=[row],
            booking_url="https://ctrip.example.test/book",
            h5_fallback_url="https://ctrip.example.test/book",
            inventory_expires_at="2000-01-01T00:00:00+00:00",
        )
    )
    assert dto.winning_price_id == "ctrip-stale-cny"


@pytest.mark.parametrize(
    ("row_overrides", "card_overrides"),
    [
        ({"data_provider": "serpapi_google_flights"}, {}),
        ({"url": None}, {"booking_url": None, "h5_fallback_url": None}),
        ({"provider_status": "success"}, {}),
    ],
)
def test_deal_card_rejects_stale_winner_outside_ctrip_contract(
    row_overrides,
    card_overrides,
):
    from backend.schemas.common import DealCardDto

    row = {
        **_deal_payload()["prices"][0],
        "id": "ctrip-stale-cny",
        "name": "携程",
        "price": 500,
        "lowest": True,
        "price_status": "stale",
        "provider_status": "stale",
        "url": "https://ctrip.example.test/book",
        "data_provider": "ctrip_snapshot",
        "data_freshness": "stale",
        "expires_at": "2000-01-01T00:00:00+00:00",
        **row_overrides,
    }

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(
            {
                **_deal_payload(
                    platform="携程",
                    price=500,
                    lowest_price=500,
                    total_price=500,
                    winning_price_id="ctrip-stale-cny",
                    data_freshness="stale",
                    prices=[row],
                    booking_url="https://ctrip.example.test/book",
                    h5_fallback_url="https://ctrip.example.test/book",
                    inventory_expires_at="2000-01-01T00:00:00+00:00",
                ),
                **card_overrides,
            }
        )


@pytest.mark.parametrize("nonwinner_lowest", [True, None])
def test_deal_card_requires_every_nonwinner_to_have_lowest_false(
    nonwinner_lowest,
):
    from backend.schemas.common import DealCardDto

    payload = _deal_payload()
    payload["prices"].append(
        {
            **payload["prices"][0],
            "id": "legacy-other-cny",
            "name": "other",
            "price": 2680,
            "lowest": nonwinner_lowest,
            "url": None,
        }
    )

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(payload)


def test_deal_card_without_a_winner_requires_lowest_false():
    from backend.schemas.common import DealCardDto

    payload = _deal_payload(
        platform="",
        price=None,
        lowest_price=None,
        total_price=None,
        winning_price_id=None,
        data_freshness="unknown",
        prices=[
            {
                **_deal_payload()["prices"][0],
                "lowest": None,
                "price_status": "stale",
                "provider_status": "stale",
                "url": None,
                "data_freshness": "unknown",
            }
        ],
        booking_url=None,
        inventory_expires_at=None,
    )

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(payload)


def test_deal_card_rejects_booking_fallback_without_matching_winner():
    from backend.schemas.common import DealCardDto

    with pytest.raises(ValidationError):
        DealCardDto.model_validate(
            _deal_payload(
                h5_fallback_url="https://other.example.test/book"
            )
        )

    reference_payload = _deal_payload(
        platform="",
        price=None,
        lowest_price=None,
        total_price=None,
        winning_price_id=None,
        prices=[
            {
                **_deal_payload()["prices"][0],
                "lowest": False,
            }
        ],
        h5_fallback_url="https://other.example.test/book",
    )
    with pytest.raises(ValidationError):
        DealCardDto.model_validate(reference_payload)


# ── ApiMeta ───────────────────────────────────────────────────────────────────

def test_api_meta_optional_fields():
    """ApiMeta 只有 generated_at 必填，其余可选。"""
    from backend.schemas.common import ApiMeta

    meta = ApiMeta.model_validate({"generated_at": "2026-04-12T00:00:00Z"})
    assert meta.generated_at == "2026-04-12T00:00:00Z"
    assert meta.source is None
    assert meta.fallback_mode is None


# ── SearchResponseDto ─────────────────────────────────────────────────────────

def test_search_query_accepts_authoritative_airport_scope_without_intent_text():
    from backend.schemas.search import SearchQueryDto

    dto = SearchQueryDto.model_validate(
        {
            "origin_city": "北京",
            "origin_code": "BJS",
            "origin_airport_ids": ["PEK", "PKX"],
            "origin_airport_scope": None,
            "destination_city": "长治",
            "destination_code": "CIH",
            "destination_airport_ids": ["CIH"],
            "destination_airport_scope": "CIH",
            "date_start": "2026-07-26",
            "date_end": "2026-07-26",
        }
    )

    assert dto.raw_text == ""
    assert dto.normalized_text == ""
    assert dto.origin_airport_ids == ["PEK", "PKX"]
    assert dto.origin_airport_scope is None
    assert dto.destination_airport_ids == ["CIH"]
    assert dto.destination_airport_scope == "CIH"


def test_search_response_structure():
    """SearchResponseDto 含 user_id / query / deals / analysis / recommendation / meta。"""
    from backend.schemas.search import SearchResponseDto, SearchQueryDto, SearchAnalysisDto, SearchRecommendationDto
    from backend.schemas.common import ApiMeta

    dto = SearchResponseDto.model_validate({
        "user_id": "demo-user",
        "query": {
            "raw_text": "北京到东京",
            "normalized_text": "PEK->NRT",
            "origin_city": "北京",
            "origin_code": "PEK",
            "destination_city": "东京",
            "destination_code": "NRT",
            "date_start": "2026-05-01",
            "date_end": "2026-05-03",
            "budget": None,
        },
        "deals": [_deal_payload()],
        "analysis": {
            "min_price": 2580,
            "max_price": 4200,
            "avg_price": 3100,
            "avg_90d": 3300,
            "lower_than_avg": 0.15,
            "price_spread_pct": 0.38,
            "match_score": 0.8,
            "within_budget": False,
            "matched_preferences": ["preferred_destinations"],
        },
        "recommendation": {
            "action": "buy_now",
            "text": "建议现在购买",
            "confidence": "high",
            "signals": ["低于均价15%"],
        },
        "meta": {"generated_at": "2026-04-12T00:00:00Z"},
    })

    assert dto.user_id == "demo-user"
    assert len(dto.deals) == 1
    assert dto.deals[0].system_id == "SYS.042"
    assert dto.analysis.match_score == 0.8
    assert dto.recommendation.action == "buy_now"


# ── MemoryResponseDto ─────────────────────────────────────────────────────────

def test_memory_response_uses_memories_field():
    """MemoryResponseDto 使用 memories 字段（不是 preferences）。"""
    from backend.schemas.memory import MemoryResponseDto

    dto = MemoryResponseDto.model_validate({
        "user_id": "demo-user",
        "memories": [
            {
                "id": "mem-1",
                "field": "price_anchor",
                "label": "心理价位",
                "value": 3000,
                "value_display": "3000元",
                "source": "manual",
                "updated_at": "2026-04-12T00:00:00Z",
            }
        ],
        "query_history": [],
        "click_history": [],
        "meta": {"generated_at": "2026-04-12T00:00:00Z"},
    })

    assert hasattr(dto, "memories")
    assert not hasattr(dto, "preferences")
    assert dto.memories[0].field == "price_anchor"
    assert dto.memories[0].label == "心理价位"
    assert dto.memories[0].value_display == "3000元"


def test_memory_response_empty_memories():
    """memories 为空列表时也能正常 validate。"""
    from backend.schemas.memory import MemoryResponseDto

    dto = MemoryResponseDto.model_validate({
        "user_id": "demo-user",
        "memories": [],
        "query_history": [],
        "click_history": [],
        "meta": {"generated_at": "2026-04-12T00:00:00Z"},
    })
    assert dto.memories == []


# ── RecommendationCardDto ─────────────────────────────────────────────────────

def test_recommendation_card_dto():
    """RecommendationCardDto 含 id / title / reason / query_hint / tags / preview_deal。"""
    from backend.schemas.common import RecommendationCardDto

    dto = RecommendationCardDto.model_validate({
        "id": "rec-001",
        "title": "五一特价 北京→东京",
        "reason": "近30天最低价",
        "query_hint": "北京到东京五一",
        "tags": ["特价", "直飞"],
        "preview_deal": None,
    })
    assert dto.id == "rec-001"
    assert dto.tags == ["特价", "直飞"]
    assert dto.preview_deal is None
