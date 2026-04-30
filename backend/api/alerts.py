from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from backend.schemas.alerts import (
    AlertCreateRequest,
    AlertCreateResponseDto,
    AlertItemDto,
    AlertsListResponseDto,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=AlertCreateResponseDto)
async def create_alert(payload: AlertCreateRequest, request: Request) -> AlertCreateResponseDto:
    alert_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            from backend.db.models import PriceAlert
            async with session_factory() as db:
                db.add(PriceAlert(
                    alert_id=alert_id,
                    user_id=payload.user_id,
                    flight_id=payload.flight_id,
                    origin_city=payload.origin_city,
                    destination_city=payload.destination_city,
                    depart_date=payload.depart_date,
                    current_price=payload.current_price,
                    target_price=payload.target_price,
                    status="active",
                ))
                await db.commit()
        except Exception:
            pass

    return AlertCreateResponseDto(alert_id=alert_id, status="active", created_at=now)


@router.get("", response_model=AlertsListResponseDto)
async def list_alerts(
    request: Request,
    user_id: str = Query(default="demo-user"),
) -> AlertsListResponseDto:
    alerts: list[AlertItemDto] = []

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory:
        try:
            from sqlalchemy import select
            from backend.db.models import PriceAlert
            async with session_factory() as db:
                stmt = (
                    select(PriceAlert)
                    .where(PriceAlert.user_id == user_id)
                    .order_by(PriceAlert.created_at.desc())
                )
                rows = (await db.execute(stmt)).scalars().all()
                alerts = [
                    AlertItemDto(
                        alert_id=r.alert_id,
                        origin_city=r.origin_city,
                        destination_city=r.destination_city,
                        depart_date=r.depart_date,
                        current_price=r.current_price,
                        target_price=r.target_price,
                        status=r.status,
                        created_at=str(r.created_at),
                    )
                    for r in rows
                ]
        except Exception:
            pass

    return AlertsListResponseDto(user_id=user_id, alerts=alerts)
