from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from backend.api._deps import current_user_id
from backend.application.services.flight_dates import (
    validate_canonical_depart_date,
)
from backend.config import settings
from backend.infrastructure.db.alert_repo import (
    create_alert,
    get_alert_for_user,
    list_alerts,
    mark_alert_notification_status,
    update_alert_status,
)
from backend.infrastructure.db.notification_repo import (
    upsert_alert_subscription,
)
from backend.infrastructure.db.wechat_repo import get_wechat_account_for_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


class CreateAlertReq(BaseModel):
    origin: str
    destination: str
    depart_date: str
    target_price: int
    current_price: int | None = None
    currency: str = "CNY"
    notify_wechat: bool = False

    @field_validator("depart_date")
    @classmethod
    def validate_depart_date(cls, value: str) -> str:
        return validate_canonical_depart_date(value)


@router.post("", status_code=201)
async def create(req: CreateAlertReq, uid: str = Depends(current_user_id)):
    if req.currency != "CNY":
        raise HTTPException(422, "price alerts currently support CNY only")
    wechat_account = None
    if req.notify_wechat:
        if not settings.wechat_price_alert_template_id:
            raise HTTPException(503, "wechat price alert template is not configured")
        wechat_account = await get_wechat_account_for_user(uid)
        if wechat_account is None:
            raise HTTPException(409, "wechat account is not linked")

    aid = await create_alert(
        uid,
        origin=req.origin,
        destination=req.destination,
        depart_date=req.depart_date,
        target_price=req.target_price,
        current_price=req.current_price,
        currency=req.currency,
        notification_status=("subscribed" if req.notify_wechat else "not_requested"),
    )
    if req.notify_wechat and wechat_account is not None:
        await upsert_alert_subscription(
            alert_id=aid,
            user_id=uid,
            channel="wechat",
            template_id=settings.wechat_price_alert_template_id,
        )
    return {
        "id": aid,
        "wechat_notification": ("subscribed" if req.notify_wechat else "not_requested"),
    }


@router.get("")
async def list_(uid: str = Depends(current_user_id)):
    rows = await list_alerts(uid)
    return {
        "alerts": [
            {
                "id": a.id,
                "origin": a.origin,
                "destination": a.destination,
                "depart_date": a.depart_date,
                "target_price": a.target_price,
                "current_price": a.current_price,
                "latest_price": a.latest_price,
                "latest_provider": a.latest_provider,
                "latest_quote_at": (
                    a.latest_quote_at.isoformat()
                    if a.latest_quote_at is not None
                    else None
                ),
                "currency": a.currency,
                "notification_status": a.notification_status,
                "status": a.status,
            }
            for a in rows
        ]
    }


@router.get("/{alert_id}")
async def get_(alert_id: str, uid: str = Depends(current_user_id)):
    alert = await get_alert_for_user(alert_id, uid)
    if alert is None:
        raise HTTPException(404, "alert not found")
    return {
        "id": alert.id,
        "origin": alert.origin,
        "destination": alert.destination,
        "depart_date": alert.depart_date,
        "target_price": alert.target_price,
        "current_price": alert.current_price,
        "latest_price": alert.latest_price,
        "latest_provider": alert.latest_provider,
        "latest_quote_at": (
            alert.latest_quote_at.isoformat()
            if alert.latest_quote_at is not None
            else None
        ),
        "currency": alert.currency,
        "notification_status": alert.notification_status,
        "status": alert.status,
    }


@router.post("/{alert_id}/wechat-subscription")
async def subscribe_wechat(alert_id: str, uid: str = Depends(current_user_id)):
    if not settings.wechat_price_alert_template_id:
        raise HTTPException(503, "wechat price alert template is not configured")
    alert = await get_alert_for_user(alert_id, uid)
    if alert is None:
        raise HTTPException(404, "alert not found")
    if alert.status not in {"active", "paused"}:
        raise HTTPException(409, "only active or paused alerts can subscribe")
    if await get_wechat_account_for_user(uid) is None:
        raise HTTPException(409, "wechat account is not linked")
    await upsert_alert_subscription(
        alert_id=alert_id,
        user_id=uid,
        channel="wechat",
        template_id=settings.wechat_price_alert_template_id,
    )
    await mark_alert_notification_status(alert_id, "subscribed")
    return {"id": alert_id, "wechat_notification": "subscribed"}


class UpdateAlertReq(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"active", "paused", "cancelled"}:
            raise ValueError("status must be active, paused, or cancelled")
        return value


@router.patch("/{alert_id}")
async def update_(
    alert_id: str,
    req: UpdateAlertReq,
    uid: str = Depends(current_user_id),
):
    if not await update_alert_status(alert_id, uid, status=req.status):
        raise HTTPException(404, "alert not found")
    return {"id": alert_id, "status": req.status}
