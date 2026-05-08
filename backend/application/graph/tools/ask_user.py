from __future__ import annotations

from langchain_core.tools import tool

_QUESTIONS = {
    "origin": "你想从哪个城市出发？",
    "destination": "想去哪个城市？",
    "depart_date": "出发日期是哪天？例如「明天」或「5月8日」",
    "budget": "你的预算大概多少？",
}


@tool
async def ask_user(missing_field: str, context: str) -> str:
    """向用户追问一个缺失的关键槽位（origin / destination / depart_date / budget）。"""
    return _QUESTIONS.get(missing_field, "可以再补充一下吗？")
