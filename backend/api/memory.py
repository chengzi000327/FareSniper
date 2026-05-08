from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.infrastructure.db.memory_repo import delete_field, list_memories, upsert_memory
from backend.infrastructure.db.query_history_repo import list_query_history

router = APIRouter(prefix="/memory", tags=["memory"])


class PatchReq(BaseModel):
    field: str
    value: Any


class MemoryItemOut(BaseModel):
    field: str
    value: Any
    source: str


class QueryHistoryItemOut(BaseModel):
    query: str
    at: str


class MemoryRsp(BaseModel):
    memories: list[MemoryItemOut]
    query_history: list[QueryHistoryItemOut]


@router.get("", response_model=MemoryRsp)
async def get_memory(uid: str = Depends(current_user_id)) -> MemoryRsp:
    rows = await list_memories(uid)
    qh = await list_query_history(uid, limit=20)
    return MemoryRsp(
        memories=[
            MemoryItemOut(field=m.field, value=m.value, source=m.source) for m in rows
        ],
        query_history=[
            QueryHistoryItemOut(query=q.query_text, at=q.created_at.isoformat())
            for q in qh
        ],
    )


@router.patch("")
async def patch_memory(req: PatchReq, uid: str = Depends(current_user_id)):
    await upsert_memory(uid, req.field, req.value, source="user")
    return {"ok": True}


@router.delete("/{field}", status_code=204)
async def delete_memory_field(
    field: str, uid: str = Depends(current_user_id)
) -> Response:
    await delete_field(uid, field)
    return Response(status_code=204)
