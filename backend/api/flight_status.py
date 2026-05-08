from fastapi import APIRouter
from backend.application.services.flight_status import fetch_status

router = APIRouter(tags=["flight_status"])


@router.get("/flight_status")
async def get_status(flight_no: str, date: str):
    return await fetch_status(flight_no, date)
