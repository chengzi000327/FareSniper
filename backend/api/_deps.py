"""Shared FastAPI dependencies.

``current_user_id`` validates a Bearer JWT and returns the ``sub`` claim.
All protected endpoints in TG-06 / TG-09 / TG-12 inject this dep so the
auth contract has exactly one definition.
"""
from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Header, HTTPException, status

from backend.config import settings


def current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {exc}"
        ) from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="token missing sub"
        )
    return sub
