from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.factory import get_graph

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger("faresniper.search")


class SearchReq(BaseModel):
    session_id: str | None = None
    message: str


@router.post("", response_model=FrontendResponse)
async def search(
    req: SearchReq, uid: str = Depends(current_user_id)
) -> FrontendResponse:
    request_id = uuid.uuid4().hex
    t0 = time.monotonic()
    logger.info(
        "search_start request_id=%s user_id=%s session_id=%s message_len=%s",
        request_id,
        uid,
        req.session_id,
        len(req.message),
    )
    graph = get_graph()
    try:
        out = await graph.ainvoke(
            {
                "request_id": request_id,
                "request_user_id": uid,
                "request_session_id": req.session_id,
                "messages": [HumanMessage(content=req.message)],
                "clarify_count": 0,
                "fallback_triggered": False,
                "errors": [],
            },
            config={"recursion_limit": 15},
        )
    except Exception:
        logger.exception(
            "search_graph_failed request_id=%s user_id=%s session_id=%s duration_ms=%s",
            request_id,
            uid,
            req.session_id,
            int((time.monotonic() - t0) * 1000),
        )
        raise
    rsp: FrontendResponse = out["response"]
    rsp.session_id = out.get("request_session_id")
    logger.info(
        "search_done request_id=%s user_id=%s session_id=%s deals=%s fallback=%s duration_ms=%s",
        request_id,
        uid,
        rsp.session_id,
        len(rsp.deals),
        rsp.meta.get("fallback_mode") if rsp.meta else None,
        int((time.monotonic() - t0) * 1000),
    )
    return rsp
