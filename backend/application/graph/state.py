"""SearchGraph runtime state."""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from backend.application.contracts.decision import DecisionResult, FrontendResponse
from backend.application.contracts.intent_registry import IntentDefinition
from backend.application.contracts.intent import SlotBundle
from backend.application.contracts.preference import PreferenceMatchResult
from backend.application.contracts.search import FlightSearchResult
from backend.application.contracts.workflow import WorkflowError


class WorkflowState(TypedDict, total=False):
    # ── ReAct graph fields (TG-08) ──────────────────────────────────────────
    messages: Annotated[list, add_messages]
    accumulated_slots: SlotBundle | None
    fallback_triggered: bool
    alert_result: dict | None
    missing_slots: list[str]
    intent_definitions: list[IntentDefinition]

    # ── Common fields ────────────────────────────────────────────────────────
    request_user_id: str
    request_session_id: str | None
    clarify_count: int
    search_result: FlightSearchResult | None
    pref_result: PreferenceMatchResult | None
    decision: DecisionResult | None
    response: FrontendResponse | None
    errors: list[WorkflowError]

    # ── Legacy DAG fields (removed in TG-19) ─────────────────────────────────
    request_message: str
    context: Any
    intent: Any
    _session_factory: Any
    _redis_client: Any
