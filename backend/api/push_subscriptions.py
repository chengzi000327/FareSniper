"""WebPush subscription persistence endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.infrastructure.db.push_subscription_repo import upsert_subscription

router = APIRouter(prefix="/push", tags=["push"])


class PushSubscriptionReq(BaseModel):
    subscription: dict


@router.post("/subscriptions", status_code=204)
async def save_subscription(
    req: PushSubscriptionReq,
    uid: str = Depends(current_user_id),
) -> Response:
    await upsert_subscription(uid, req.subscription)
    return Response(status_code=204)
