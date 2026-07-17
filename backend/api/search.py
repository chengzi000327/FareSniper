from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from backend.api._deps import current_user_id
from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.factory import get_graph
from backend.application.services.search_events import (
    SearchEventEmitter,
    bind_search_event_emitter,
    emit_search_event,
)

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger("faresniper.search")


class SearchReq(BaseModel):
    session_id: str | None = None
    message: str


async def _invoke_graph(
    req: SearchReq,
    request: Request,
    uid: str,
    request_id: str,
) -> FrontendResponse:
    graph = get_graph()
    out = await graph.ainvoke(
        {
            "request_id": request_id,
            "request_user_id": uid,
            "request_session_id": req.session_id,
            "request_message": req.message,
            "messages": [HumanMessage(content=req.message)],
            "clarify_count": 0,
            "fallback_triggered": False,
            "errors": [],
            "_session_factory": getattr(request.app.state, "session_factory", None),
            "_redis_client": getattr(request.app.state, "redis_client", None),
        },
        config={"recursion_limit": 15},
    )
    response: FrontendResponse = out["response"]
    response.session_id = out.get("request_session_id")
    emit_search_event("complete", {"response": response.model_dump(mode="json")})
    return response


@router.post("", response_model=FrontendResponse)
async def search(
    req: SearchReq, request: Request, uid: str = Depends(current_user_id)
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
    try:
        rsp = await _invoke_graph(req, request, uid, request_id)
    except Exception:
        logger.exception(
            "search_graph_failed request_id=%s user_id=%s session_id=%s duration_ms=%s",
            request_id,
            uid,
            req.session_id,
            int((time.monotonic() - t0) * 1000),
        )
        raise
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


@router.post("/stream")
async def search_stream(
    req: SearchReq, request: Request, uid: str = Depends(current_user_id)
) -> StreamingResponse:
    request_id = uuid.uuid4().hex
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    complete_emitted = False

    def enqueue(event: dict) -> None:
        nonlocal complete_emitted
        if event["type"] == "complete":
            complete_emitted = True
        queue.put_nowait(event)

    emitter = SearchEventEmitter(request_id, enqueue)

    async def run_graph() -> None:
        try:
            with bind_search_event_emitter(emitter):
                await _invoke_graph(req, request, uid, request_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("search_stream_failed request_id=%s", request_id)
            if not complete_emitted:
                emitter.emit(
                    "complete",
                    {
                        "error": "search_failed",
                        "message": "搜索暂时不可用，请稍后重试",
                    },
                )
        finally:
            queue.put_nowait(None)

    async def body():
        task = asyncio.create_task(run_graph())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
