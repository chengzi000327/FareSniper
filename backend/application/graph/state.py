"""SearchGraph runtime state."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

from backend.application.context.assembler import ContextEnvelope
from backend.application.contracts.decision import DecisionResult, FrontendResponse
from backend.application.contracts.intent import NormalizedIntent
from backend.application.contracts.preference import PreferenceMatchResult
from backend.application.contracts.search import FlightSearchResult
from backend.application.contracts.workflow import WorkflowError


class WorkflowState(TypedDict):
    request_user_id: str
    request_session_id: str | None
    request_message: str
    context: ContextEnvelope | None
    clarify_count: int
    intent: NormalizedIntent | None
    search_result: FlightSearchResult | None
    pref_result: PreferenceMatchResult | None
    decision: DecisionResult | None
    response: FrontendResponse | None
    errors: list[WorkflowError]
    _session_factory: Any
    _redis_client: Any
