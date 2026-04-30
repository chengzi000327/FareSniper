from unittest.mock import AsyncMock, patch

import pytest

from backend.application.contracts.intent import DateWindow, LocationRef, NormalizedIntent


def _base_state(**overrides):
    base = dict(
        request_user_id="test",
        request_session_id=None,
        request_message="北京到三亚五一直飞",
        context=None,
        clarify_count=0,
        intent=None,
        search_result=None,
        pref_result=None,
        decision=None,
        response=None,
        errors=[],
        _session_factory=None,
        _redis_client=None,
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_complete_intent_returns_deals():
    """完整意图 -> run_flight_search -> render_response -> deals 非空。"""
    from backend.application.graph.factory import search_graph

    complete_intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=complete_intent)
        result = await search_graph.ainvoke(_base_state())

    assert result["response"] is not None
    assert len(result["response"].deals) > 0
    assert result["response"].recommendation.get("action") in ("buy_now", "watch", "skip")


@pytest.mark.asyncio
async def test_incomplete_intent_returns_clarify():
    """不完整意图 -> clarify_response -> deals=[]，含追问文本。"""
    from backend.application.graph.factory import search_graph

    incomplete = NormalizedIntent(
        destination=LocationRef(city="三亚", iata_code="SYX"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=incomplete)
        result = await search_graph.ainvoke(_base_state(request_message="我想去三亚"))

    assert result["response"].deals == []
    assert "请问" in result["response"].recommendation.get("text", "")


@pytest.mark.asyncio
async def test_parse_failed_returns_clarify():
    """解析失败 -> 走 clarify 路径。"""
    from backend.application.graph.factory import search_graph

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=NormalizedIntent(parse_failed=True))
        result = await search_graph.ainvoke(_base_state(request_message="随便"))

    assert result["response"].deals == []


@pytest.mark.asyncio
async def test_response_passes_searchresponsedto_validation():
    """FrontendResponse payload should validate as SearchResponseDto."""
    from backend.application.graph.factory import search_graph
    from backend.schemas.search import SearchResponseDto

    complete_intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=complete_intent)
        result = await search_graph.ainvoke(_base_state())

    assert result["response"] is not None
    dto = SearchResponseDto.model_validate(result["response"].model_dump())
    assert len(dto.deals) > 0
    assert dto.query.raw_text == "北京到三亚五一直飞"
    assert dto.recommendation.action in ("buy_now", "watch", "skip")
