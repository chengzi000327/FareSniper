from __future__ import annotations

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.factory import get_graph

router = APIRouter(prefix="/search", tags=["search"])


class SearchReq(BaseModel):
    session_id: str | None = None
    message: str


@router.post("", response_model=FrontendResponse)
async def search(
    req: SearchReq, uid: str = Depends(current_user_id)
) -> FrontendResponse:
    graph = get_graph()
    out = await graph.ainvoke(
        {
            "request_user_id": uid,
            "request_session_id": req.session_id,
            "messages": [HumanMessage(content=req.message)],
            "clarify_count": 0,
            "fallback_triggered": False,
            "errors": [],
        },
        config={"recursion_limit": 15},
    )
    rsp: FrontendResponse = out["response"]
    rsp.session_id = out.get("request_session_id")
    return rsp
