from __future__ import annotations

import jwt
from fastapi import APIRouter, Header, HTTPException, Response

from backend.application.contracts.auth import OtpRequestDto, OtpVerifyDto
from backend.application.services.otp import issue_code, verify_code
from backend.config import settings
from backend.infrastructure.db.user_repo import find_or_create_by_phone, merge_anonymous_user
from backend.infrastructure.notifications.sms import send_sms

router = APIRouter(prefix="/auth", tags=["auth"])


def _decode_anon_user_id(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            settings.jwt_secret,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
    return payload.get("sub") if payload.get("anon") else None


@router.post("/otp", status_code=204)
async def request_otp(req: OtpRequestDto) -> Response:
    code = await issue_code(req.phone)
    await send_sms(req.phone, f"FareSniper 验证码：{code}（5 分钟内有效）")
    return Response(status_code=204)


@router.post("/verify")
async def verify(
    req: OtpVerifyDto, authorization: str | None = Header(default=None)
):
    if not await verify_code(req.phone, req.code):
        raise HTTPException(401, "invalid code")
    anon_id = _decode_anon_user_id(authorization)
    user = await find_or_create_by_phone(req.phone)
    if anon_id and anon_id != user.id:
        await merge_anonymous_user(anon_id=anon_id, target_id=user.id)
    token = jwt.encode(
        {"sub": user.id, "phone": req.phone},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"access_token": token, "user_id": user.id}
