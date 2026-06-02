"""Parse user intent node."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.application.graph._now import today_cn

from backend.application.contracts.intent import NormalizedIntent, is_intent_complete
from backend.application.contracts.workflow import WorkflowError, WorkflowErrorCode
from backend.application.graph.state import WorkflowState
from backend.infrastructure.llm.models import get_intent_model

_SYSTEM_PROMPT = """你是一个机票查询助手，专注于从用户输入中提取出行意图。

**今天是 {today}。所有相对日期都必须基于今天推算成具体的 YYYY-MM-DD：**
- "明天"=今天+1天，"后天"=今天+2天，"大后天"=今天+3天，"N天后"=今天+N天
- "这周末/本周末"=本周最近的周六；"下周末"=下一个周六；"下周X"=下一周的星期X
- 节假日按今天所在年份就近推算：五一=5月1日，清明=4月4日，端午/中秋按农历，国庆=10月1日，元旦=1月1日
- 若用户说的日期已过（早于今天），顺延到明年同一日期

从用户输入中提取：origin（出发城市）、destination（目的地）、date_window（出行日期）、budget_cny（预算）、constraints（约束列表）。

## 判断逻辑
1. origin.city：出发城市中文名，未提及为null
2. destination.city：目的地城市中文名，未提及为null
3. date_window.start_date：按上面"今天"规则推算成 YYYY-MM-DD，未提及为null

## 约束识别
- "不要太早"/"不要红眼" → constraints: [{{"type":"avoid_redeye","value":true}}]
- "直飞" → constraints: [{{"type":"direct_only","value":true}}]
- "尽量早点到" → constraints: [{{"type":"prefer_morning","value":true}}]

## 城市→机场代码（常用）
北京=BJS 上海=SHA 广州=CAN 成都=CTU 三亚=SYX 杭州=HGH 重庆=CKG 西安=XIY

## 输出格式（严格 JSON，符合 NormalizedIntent schema）
{{"origin":{{"city":"北京","iata_code":"BJS"}},"destination":{{"city":"三亚","iata_code":"SYX"}},
"date_window":{{"start_date":"2026-05-01","end_date":"2026-05-05"}},"budget_cny":600,
"constraints":[{{"type":"avoid_redeye","value":true}}],"parse_failed":false}}

不确定字段填null，只输出JSON。"""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history", optional=True),
        ("human", "{message}"),
    ]
)


def _build_chain():
    model = get_intent_model()
    try:
        return _prompt | model.with_structured_output(NormalizedIntent)
    except Exception:

        class _JsonParser:
            async def ainvoke(self, inputs):
                raw = await (_prompt | model).ainvoke(inputs)
                try:
                    data = json.loads(raw.content if hasattr(raw, "content") else raw)
                    return NormalizedIntent(**data)
                except Exception:
                    return NormalizedIntent(parse_failed=True)

        return _JsonParser()


_intent_chain = _build_chain()


async def parse_user_intent(state: WorkflowState) -> WorkflowState:
    ctx = state.get("context")
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in (ctx.session_history if ctx else [])[-4:]
    ]
    try:
        intent = await _intent_chain.ainvoke(
            {"message": state["request_message"], "history": history, "today": today_cn()}
        )
    except Exception:
        intent = NormalizedIntent(parse_failed=True)

    if not intent.raw_text:
        intent.raw_text = state["request_message"]

    errors = list(state.get("errors") or [])
    if intent.parse_failed:
        errors.append(
            WorkflowError(
                code=WorkflowErrorCode.parse_failed,
                message="意图解析失败",
                node="parse_user_intent",
            )
        )
    return {**state, "intent": intent, "errors": errors}


def route_after_intent(state: WorkflowState) -> str:
    intent = state.get("intent")
    if not intent or intent.parse_failed:
        return "clarify"
    if is_intent_complete(intent):
        return "complete"
    return "clarify"
