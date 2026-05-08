from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings
from backend.infrastructure.db.user_repo import allocate_anonymous

router = APIRouter(prefix="/session", tags=["session"])


class SessionReq(BaseModel):
    user_id: str | None = None


class SessionRsp(BaseModel):
    user_id: str
    session_id: str
    access_token: str


@router.post("", response_model=SessionRsp)
async def create_session(req: SessionReq) -> SessionRsp:
    user_id = req.user_id or await allocate_anonymous()
    session_id = f"s_{uuid.uuid4().hex[:12]}"
    token = jwt.encode(
        {"sub": user_id, "anon": True}, settings.jwt_secret, algorithm="HS256"
    )
    return SessionRsp(user_id=user_id, session_id=session_id, access_token=token)
