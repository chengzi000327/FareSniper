from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas.memory import MemoryPatchRequest, MemoryResponseDto

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=MemoryResponseDto)
async def get_memory(
    request: Request,
    user_id: str = Query(default="demo-user"),
) -> MemoryResponseDto:
    result = await request.app.state.recommendation_service.get_memory(user_id)
    return MemoryResponseDto.model_validate(result)


@router.patch("", response_model=MemoryResponseDto)
async def patch_memory(payload: MemoryPatchRequest, request: Request) -> MemoryResponseDto:
    result = await request.app.state.recommendation_service.patch_memory(
        user_id=payload.user_id,
        field=payload.field,
        value=payload.value,
        source=payload.source,
    )
    return MemoryResponseDto.model_validate(result)


@router.delete("/{field}", response_model=MemoryResponseDto)
async def delete_memory_field(
    field: str,
    request: Request,
    user_id: str = Query(default="demo-user"),
) -> MemoryResponseDto:
    result = await request.app.state.recommendation_service.delete_memory_field(
        user_id=user_id,
        field=field,
    )
    return MemoryResponseDto.model_validate(result)
