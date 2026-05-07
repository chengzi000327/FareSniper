"""Phone-OTP authentication endpoints.

The handlers here are placeholders. TG-12 · Task 1-3 replace them with
real OTP send / verify implementations (Aliyun + Twilio fallback) and
JWT minting that consumes ``backend.api._deps.current_user_id``.
"""
from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def send_otp() -> dict:
    """Send an OTP code to the supplied phone. Implemented in TG-12 · Task 1."""
    return {"detail": "not_implemented"}


@router.post("/verify", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def verify_otp() -> dict:
    """Verify the OTP and mint a JWT. Implemented in TG-12 · Task 2."""
    return {"detail": "not_implemented"}
