from fastapi import APIRouter, Response, Depends
from pydantic import BaseModel
from backend.analytics.events import EventName
from backend.analytics.track import track
from backend.api._deps import current_user_id

router = APIRouter(tags=["track"])


class TrackBody(BaseModel):
    event: str
    payload: dict


@router.post("/track", status_code=204)
async def post_track(body: TrackBody, uid: str = Depends(current_user_id)) -> Response:
    payload = {**body.payload, "user_id": uid}
    await track(EventName(body.event), user_id=uid, payload=payload)
    return Response(status_code=204)
