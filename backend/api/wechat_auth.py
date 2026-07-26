from __future__ import annotations

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.infrastructure.db.user_repo import merge_anonymous_user
from backend.infrastructure.db.wechat_repo import find_or_create_wechat_user
from backend.infrastructure.notifications.wechat import (
    WechatApiError,
    exchange_login_code,
)

router = APIRouter(prefix="/auth/wechat", tags=["auth"])


class WechatSessionReq(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class WechatSessionRsp(BaseModel):
    access_token: str
    user_id: str


def _wechat_login_configured() -> bool:
    return bool(
        settings.wechat_mini_app_id.strip()
        and settings.wechat_mini_app_secret.strip()
    )


def _anonymous_user_id(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None
    return str(payload["sub"]) if payload.get("anon") and payload.get("sub") else None


@router.get("/status")
async def wechat_login_status() -> dict[str, bool]:
    return {"configured": _wechat_login_configured()}


@router.post("/session", response_model=WechatSessionRsp)
async def create_wechat_session(
    req: WechatSessionReq,
    authorization: str | None = Header(default=None),
) -> WechatSessionRsp:
    if not _wechat_login_configured():
        raise HTTPException(503, "wechat login is not configured")
    try:
        wechat_session = await exchange_login_code(req.code)
    except WechatApiError as exc:
        status_code = 401 if exc.errcode in {40029, 45011} else 502
        raise HTTPException(status_code, str(exc)) from exc

    user_id = await find_or_create_wechat_user(
        app_id=settings.wechat_mini_app_id,
        open_id=wechat_session.open_id,
        union_id=wechat_session.union_id,
    )
    anonymous_user_id = _anonymous_user_id(authorization)
    if anonymous_user_id and anonymous_user_id != user_id:
        await merge_anonymous_user(
            anon_id=anonymous_user_id,
            target_id=user_id,
        )
    token = jwt.encode(
        {"sub": user_id, "provider": "wechat"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return WechatSessionRsp(access_token=token, user_id=user_id)
