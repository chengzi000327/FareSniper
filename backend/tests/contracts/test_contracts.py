import pytest

from backend.application.contracts.decision import DecisionResult, RecommendedAction
from backend.application.contracts.intent import (
    DateWindow,
    LocationRef,
    NormalizedIntent,
    is_intent_complete,
)
from backend.application.contracts.preference import PreferenceMatchResult
from backend.application.contracts.search import FlightCandidate, FlightSearchResult
from backend.application.contracts.workflow import (
    WorkflowError,
    WorkflowErrorCode,
    WorkflowRequest,
)


def test_workflow_request_requires_user_id_and_message():
    req = WorkflowRequest(user_id="u1", message="北京去三亚")
    assert req.user_id == "u1"


def test_workflow_request_rejects_extra_fields():
    with pytest.raises(Exception):
        WorkflowRequest(user_id="u1", message="test", unknown_field="x")


def test_workflow_error_code_is_enum():
    err = WorkflowError(code=WorkflowErrorCode.parse_failed, message="解析失败")
    assert err.code == "parse_failed"


def test_normalized_intent_complete():
    intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
    )
    assert is_intent_complete(intent) is True


def test_normalized_intent_incomplete_missing_origin():
    intent = NormalizedIntent(
        destination=LocationRef(city="三亚"),
        date_window=DateWindow(start_date="2026-05-01"),
    )
    assert is_intent_complete(intent) is False


def test_flight_candidate_has_required_fields():
    f = FlightCandidate(
        flight_no="HU7833",
        airline="海南航空",
        depart_time="09:30",
        arrive_time="14:20",
        duration="4h50m",
        depart_date="2026-05-01",
        price=389,
        lowest_price=389,
    )
    assert f.flight_no == "HU7833"


def test_search_result_accepts_candidates():
    f = FlightCandidate(
        flight_no="HU7833",
        airline="海南航空",
        depart_time="09:30",
        arrive_time="14:20",
        duration="4h50m",
        depart_date="2026-05-01",
    )
    result = FlightSearchResult(candidates=[f])
    assert result.candidates[0].flight_no == "HU7833"


def test_preference_match_result_defaults_to_empty_items():
    result = PreferenceMatchResult()
    assert result.items == []


def test_decision_result_enum_action():
    d = DecisionResult(action=RecommendedAction.buy_now, text="建议现在买")
    assert d.action == "buy_now"
