from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/session", tags=["session"])


class SessionCreateRequest(BaseModel):
    user_id: str = "demo-user"


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str


@router.post("", response_model=SessionCreateResponse)
async def create_session(payload: SessionCreateRequest, request: Request) -> SessionCreateResponse:
    session_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            from backend.db.models import Session as SessionModel
            async with session_factory() as db:
                db.add(SessionModel(session_id=session_id, user_id=payload.user_id))
                await db.commit()
        except Exception:
            pass

    return SessionCreateResponse(session_id=session_id, created_at=now)
