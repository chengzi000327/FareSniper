from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from backend.api._deps import current_user_id
from backend.infrastructure.db.memory_repo import (
    clear_preference_override,
    delete_field,
    get_user_preferences,
    list_memories,
    upsert_preference_override,
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

_PREFERENCE_FIELD_ALIASES = {
    "budget_ceiling": "budget",
    "price_anchor": "budget",
}

_FIELD_LABELS = {
    "budget": "心理价位",
    "budget_ceiling": "预算上限",
    "price_anchor": "心理价位",
    "frequent_cities": "常去城市",
    "preferred_airlines": "偏好航司",
    "constraints": "出行习惯",
    "travel_scenes": "出行场景",
    "seat_preference": "座位偏好",
    "companion_profile": "旅伴档案",
    "travel_ideas": "出行想法",
}

_VALUE_LABELS = {
    "direct_only": "只看直飞",
    "avoid_redeye": "避开红眼航班",
    "prefer_morning": "偏好上午出发",
    "morning": "偏好上午出发",
    "prefer_window": "偏好靠窗座位",
    "avoid_stopover": "不要中转",
    "no_stopover": "不要中转",
    "checked_baggage": "需要托运行李",
    "carry_on_only": "只带随身行李",
    "business": "商务出行",
    "leisure": "休闲旅行",
    "family_visit": "探亲回家",
    "return_home": "回家",
    "with_family": "家庭出行",
    "with_children": "亲子出行",
    "solo": "独自出行",
}


def _has_meaningful_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _display_value(field: str, value: Any) -> str:
    if value is None or value == [] or value == "":
        return "尚未学习"
    if field in {"budget", "budget_ceiling", "price_anchor"} and isinstance(
        value, (int, float)
    ):
        return f"¥{value:g}"
    if isinstance(value, list):
        displayed = []
        for item in value:
            text = str(item)
            label = _VALUE_LABELS.get(text)
            if label is None and re.fullmatch(r"[a-z][a-z0-9_]*", text):
                if field == "constraints":
                    label = "其他出行要求"
                elif field == "travel_scenes":
                    label = "其他出行场景"
                else:
                    label = "其他偏好"
            displayed.append(str(label if label is not None else item))
        return "、".join(displayed)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "是" if value else "否"
    text = str(value)
    label = _VALUE_LABELS.get(text)
    if label is None and re.fullmatch(r"[a-z][a-z0-9_]*", text):
        label = "其他偏好"
    return str(label if label is not None else value)


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


def _canonical_field(field: str) -> str:
    return _PREFERENCE_FIELD_ALIASES.get(field, field)


def _normalize_preference_value(field: str, value: Any) -> int | list[str]:
    if field == "budget":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail="心理价位必须是数字")
        normalized = int(value)
        if normalized <= 0 or normalized >= 1_000_000:
            raise HTTPException(status_code=422, detail="心理价位超出有效范围")
        return normalized

    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail="该偏好必须是文字列表")
    normalized_items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise HTTPException(status_code=422, detail="偏好列表包含无效内容")
        text = item.strip()
        if text not in normalized_items:
            normalized_items.append(text)
    return normalized_items


@router.get("", response_model=MemoryRsp)
async def get_memory(uid: str = Depends(current_user_id)) -> MemoryRsp:
    rows = await list_memories(uid)
    preferences = await get_user_preferences(uid)
    qh = await list_query_history(uid, limit=20)

    merged: dict[str, MemoryItemOut] = {}
    if preferences is not None:
        for field in _PREFERENCE_FIELDS:
            value = preferences.get(field)
            if _has_meaningful_value(value):
                merged[field] = _memory_item(field, value, source="learned")
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
    field = _canonical_field(req.field)
    if field in _PREFERENCE_FIELDS:
        value = _normalize_preference_value(field, req.value)
        await upsert_preference_override(uid, field, value)
    else:
        await upsert_memory(uid, field, req.value, source="user")
    return {"ok": True}


@router.delete("/{field}", status_code=204)
async def delete_memory_field(
    field: str, uid: str = Depends(current_user_id)
) -> Response:
    canonical_field = _canonical_field(field)
    if canonical_field in _PREFERENCE_FIELDS:
        await clear_preference_override(uid, canonical_field)
    else:
        await delete_field(uid, canonical_field)
    return Response(status_code=204)
