"""Price-history curve endpoint.

TG-09i implements the read against ``price_history_repo`` once that
table lands. Today this is a placeholder so frontend wiring (TG-13) can
target a stable URL.
"""
from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(tags=["price_history"])


@router.get("/price_history", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_price_history(origin: str | None = None, destination: str | None = None) -> dict:
    """Implemented in TG-09i · Task ?."""
    return {"detail": "not_implemented", "origin": origin, "destination": destination}
