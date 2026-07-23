from __future__ import annotations

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
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


@router.post("/session", response_model=WechatSessionRsp)
async def create_wechat_session(req: WechatSessionReq) -> WechatSessionRsp:
    if not settings.wechat_mini_app_id or not settings.wechat_mini_app_secret:
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
    token = jwt.encode(
        {"sub": user_id, "provider": "wechat"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return WechatSessionRsp(access_token=token, user_id=user_id)
