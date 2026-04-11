from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas.memory import MemoryPatchRequest, MemoryResponse


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=MemoryResponse)
async def get_memory(
    request: Request,
    user_id: str = Query(default="demo-user"),
) -> MemoryResponse:
    result = await request.app.state.memory_service.get_memory(user_id)
    return MemoryResponse(**result)


@router.patch("", response_model=MemoryResponse)
async def patch_memory(payload: MemoryPatchRequest, request: Request) -> MemoryResponse:
    result = await request.app.state.memory_service.update_preference(
        user_id=payload.user_id,
        field=payload.field,
        value=payload.value,
        source=payload.source,
    )
    return MemoryResponse(**result)
