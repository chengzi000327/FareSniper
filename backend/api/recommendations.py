from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas.memory import RecommendationsResponseDto

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponseDto)
async def get_recommendations(
    request: Request,
    user_id: str = Query(default="demo-user"),
) -> RecommendationsResponseDto:
    result = await request.app.state.recommendation_service.get_cards(user_id)
    return RecommendationsResponseDto.model_validate(result)
