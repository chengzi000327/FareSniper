"""WebPush subscription persistence endpoint.

TG-12 · Task 6+ replaces this with the real persistence into
``push_subscription_repo``. Until then frontends can register against a
stable URL that simply 501s.
"""
from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/push", tags=["push"])


@router.post("/subscriptions", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def save_subscription() -> dict:
    """Implemented in TG-12 · Task 6+ once push_subscription_repo lands."""
    return {"detail": "not_implemented"}
