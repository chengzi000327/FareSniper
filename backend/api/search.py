from __future__ import annotations

from fastapi import APIRouter, Request

from backend.application.graph.state import WorkflowState
from backend.schemas.search import SearchRequest, SearchResponseDto

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponseDto)
async def search_flights(payload: SearchRequest, request: Request) -> SearchResponseDto:
    from backend.application.graph.factory import search_graph

    initial: WorkflowState = {
        "request_user_id": payload.user_id,
        "request_session_id": payload.session_id,
        "request_message": payload.message,
        "context": None,
        "clarify_count": 0,
        "intent": None,
        "search_result": None,
        "pref_result": None,
        "decision": None,
        "response": None,
        "errors": [],
        "_session_factory": getattr(request.app.state, "session_factory", None),
        "_redis_client": getattr(request.app.state, "redis_client", None),
    }

    final = await search_graph.ainvoke(
        initial,
        config={"run_name": f"search:{payload.user_id}", "recursion_limit": 15},
    )
    return SearchResponseDto.model_validate(final["response"].model_dump())
