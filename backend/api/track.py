from fastapi import APIRouter, Response, Depends
from pydantic import BaseModel
from backend.analytics.events import EventName
from backend.analytics.track import track
from backend.api._deps import current_user_id
from backend.infrastructure.db import base as db_base
from backend.services.memory_learner import learn_from_click

router = APIRouter(tags=["track"])


class TrackBody(BaseModel):
    event: str
    payload: dict


_LEARNED_FLIGHT_FIELDS = (
    "flight_no",
    "platform",
    "price",
    "signals",
    "airline",
    "origin",
    "destination",
    "depart_date",
)


@router.post("/track", status_code=204)
async def post_track(body: TrackBody, uid: str = Depends(current_user_id)) -> Response:
    event = EventName(body.event)
    payload = {**body.payload, "user_id": uid}
    await track(event, user_id=uid, payload=payload)
    if event in {EventName.TICKET_CLICKED, EventName.PURCHASE_JUMPED}:
        flight_data = {
            field: body.payload[field]
            for field in _LEARNED_FLIGHT_FIELDS
            if field in body.payload and body.payload[field] is not None
        }
        await learn_from_click(uid, flight_data, db_base.SessionLocal)
    return Response(status_code=204)
