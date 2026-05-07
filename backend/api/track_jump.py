"""POST /api/track/jump — record purchase-jump events with deeplink status.

The user_id is derived from the JWT ``sub`` claim via
``current_user_id``; clients never supply user_id directly. This blocks
the entire class of "send anyone's analytics" exploits.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from backend.analytics.events import EventName
from backend.analytics.track import track
from backend.api._deps import current_user_id


router = APIRouter(tags=["track"])


class JumpEvent(BaseModel):
    flight_no: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)
    price: int = Field(..., ge=0)
    deeplink_ok: bool


@router.post("/track/jump", status_code=204)
async def track_jump(
    payload: JumpEvent,
    user_id: str = Depends(current_user_id),
) -> Response:
    await track(
        EventName.PURCHASE_JUMPED,
        user_id=user_id,
        payload={
            "flight_no": payload.flight_no,
            "platform": payload.platform,
            "price": payload.price,
            "deeplink_ok": "true" if payload.deeplink_ok else "false",
        },
    )
    return Response(status_code=204)
