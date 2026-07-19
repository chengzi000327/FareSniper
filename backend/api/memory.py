from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.infrastructure.db.memory_repo import (
    delete_field,
    get_user_preferences,
    list_memories,
    upsert_memory,
)
from backend.infrastructure.db.query_history_repo import list_query_history

router = APIRouter(prefix="/memory", tags=["memory"])


class PatchReq(BaseModel):
    field: str
    value: Any


class MemoryItemOut(BaseModel):
    field: str
    value: Any
    label: str
    value_display: str
    source: str


class QueryOut(BaseModel):
    text: str
    intent: dict[str, Any]


class QueryHistoryItemOut(BaseModel):
    id: int
    query: QueryOut
    created_at: str


class MemoryRsp(BaseModel):
    memories: list[MemoryItemOut]
    query_history: list[QueryHistoryItemOut]


_PREFERENCE_FIELDS = (
    "budget",
    "frequent_cities",
    "preferred_airlines",
    "constraints",
    "travel_scenes",
)

_FIELD_LABELS = {
    "budget": "心理价位",
    "budget_ceiling": "预算上限",
    "price_anchor": "心理价位",
    "frequent_cities": "常去城市",
    "preferred_airlines": "偏好航司",
    "constraints": "出行习惯",
    "travel_scenes": "出行场景",
    "seat_preference": "座位偏好",
}

_VALUE_LABELS = {
    "direct_only": "只看直飞",
    "avoid_redeye": "避开红眼航班",
    "prefer_morning": "偏好上午出发",
}


def _display_value(field: str, value: Any) -> str:
    if value is None or value == [] or value == "":
        return "尚未学习"
    if field in {"budget", "budget_ceiling", "price_anchor"} and isinstance(
        value, (int, float)
    ):
        return f"¥{value:g}"
    if isinstance(value, list):
        return "、".join(str(_VALUE_LABELS.get(str(item), item)) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(_VALUE_LABELS.get(str(value), value))


def _memory_item(field: str, value: Any, source: str) -> MemoryItemOut:
    normalized_source = {
        "learned": "auto",
        "auto": "auto",
        "user": "manual",
        "manual": "manual",
    }.get(source, source)
    return MemoryItemOut(
        field=field,
        value=value,
        label=_FIELD_LABELS.get(field, field.replace("_", " ")),
        value_display=_display_value(field, value),
        source=normalized_source,
    )


@router.get("", response_model=MemoryRsp)
async def get_memory(uid: str = Depends(current_user_id)) -> MemoryRsp:
    rows = await list_memories(uid)
    preferences = await get_user_preferences(uid)
    qh = await list_query_history(uid, limit=20)

    merged: dict[str, MemoryItemOut] = {}
    if preferences is not None:
        for field in _PREFERENCE_FIELDS:
            merged[field] = _memory_item(
                field, preferences.get(field), source="learned"
            )
    for row in rows:
        merged[row.field] = _memory_item(row.field, row.value, row.source)

    return MemoryRsp(
        memories=list(merged.values()),
        query_history=[
            QueryHistoryItemOut(
                id=q.id,
                query=QueryOut(text=q.query_text, intent=q.intent or {}),
                created_at=q.created_at.isoformat(),
            )
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
