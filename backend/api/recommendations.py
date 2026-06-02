from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api._deps import current_user_id
from backend.application.contracts.recommendations import RecommendationsResponseDto
from backend.application.services.recommendation_service import build_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponseDto)
async def get_recommendations(
    uid: str = Depends(current_user_id),
    limit: int = Query(default=6, ge=1, le=30),
    offset: int = Query(default=0, ge=0),
) -> RecommendationsResponseDto:
    return await build_recommendations(uid, limit=limit, offset=offset)
