from __future__ import annotations

from fastapi import APIRouter

from backend.application.contracts.price_history import PriceHistoryDto, PricePoint
from backend.infrastructure.db.price_history_repo import read_history

router = APIRouter(tags=["price_history"])


@router.get("/price_history", response_model=PriceHistoryDto)
async def get_price_history(
    origin: str, destination: str, days: int = 30
) -> PriceHistoryDto:
    rows = await read_history(origin, destination, days)
    return PriceHistoryDto(
        route=f"{origin}-{destination}",
        points=[PricePoint(at=r.snapshot_at.isoformat(), price=r.min_price) for r in rows],
    )
