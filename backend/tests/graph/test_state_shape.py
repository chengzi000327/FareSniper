from backend.application.graph.state import WorkflowState


def test_state_has_required_keys():
    s: WorkflowState = {
        "messages": [],
        "request_user_id": "u1",
        "request_session_id": None,
        "accumulated_slots": None,
        "clarify_count": 0,
        "fallback_triggered": False,
        "search_result": None,
        "pref_result": None,
        "decision": None,
        "alert_result": None,
        "response": None,
        "errors": [],
    }
    assert s["clarify_count"] == 0
    assert s["fallback_triggered"] is False
    assert s["accumulated_slots"] is None
    assert s["alert_result"] is None
