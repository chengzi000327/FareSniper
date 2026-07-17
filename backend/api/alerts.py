from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from backend.api._deps import current_user_id
from backend.infrastructure.db.alert_repo import create_alert, list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


class CreateAlertReq(BaseModel):
    origin: str
    destination: str
    depart_date: str
    target_price: int

    @field_validator("depart_date")
    @classmethod
    def validate_depart_date(cls, value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "depart_date must be a valid YYYY-MM-DD date"
            ) from exc
        if parsed.isoformat() != value:
            raise ValueError("depart_date must be a valid YYYY-MM-DD date")
        return value


@router.post("", status_code=201)
async def create(req: CreateAlertReq, uid: str = Depends(current_user_id)):
    aid = await create_alert(
        uid,
        origin=req.origin,
        destination=req.destination,
        depart_date=req.depart_date,
        target_price=req.target_price,
    )
    return {"id": aid}


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
                "status": a.status,
            }
            for a in rows
        ]
    }
