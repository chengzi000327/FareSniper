from __future__ import annotations

from fastapi import APIRouter, Request

from backend.schemas.search import SearchRequest, SearchResponseDto

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponseDto)
async def search_flights(payload: SearchRequest, request: Request) -> SearchResponseDto:
    result = await request.app.state.search_service.search(
        user_id=payload.user_id,
        message=payload.message,
    )
    return SearchResponseDto.model_validate(result)
