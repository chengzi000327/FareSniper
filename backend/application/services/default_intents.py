"""Built-in intent definitions used when DB/Redis registry is unavailable."""

from __future__ import annotations

from backend.application.contracts.intent_registry import IntentDefinition


DEFAULT_INTENTS: list[IntentDefinition] = [
    IntentDefinition(
        name="chitchat",
        description="闲聊、问候、身份介绍和非任务型对话",
        required_slots=[],
        optional_slots=[],
        slot_schema={},
        handler_name="chitchat",
        keywords=[
            "你好",
            "您好",
            "hello",
            "hi",
            "你是谁",
            "你叫什么",
            "介绍一下",
            "你能做什么",
            "谢谢",
            "再见",
        ],
        examples=[
            "你是谁？",
            "你好",
            "你能做什么",
            "谢谢你",
        ],
        priority=130,
    ),
    IntentDefinition(
        name="search_flight",
        description="查询机票、航班和价格",
        required_slots=["origin", "destination", "depart_date"],
        optional_slots=[
            "return_date",
            "budget",
            "constraints",
            "cabin_class",
            "passengers",
        ],
        slot_schema={
            "origin": {"type": "string", "description": "出发城市中文名"},
            "destination": {"type": "string", "description": "目的地城市中文名"},
            "depart_date": {"type": "string", "description": "出发日期 YYYY-MM-DD"},
            "budget": {"type": "integer", "description": "预算，单位人民币"},
        },
        handler_name="search_flights",
        keywords=[
            "机票",
            "航班",
            "飞机",
            "飞",
            "出发",
            "起飞",
            "到",
            "去",
            "回",
            "往返",
            "单程",
            "票",
            "价格",
            "便宜",
            "查票",
            "订票",
            "票价",
        ],
        examples=[
            "明天北京到三亚",
            "帮我找去成都的机票",
            "下周末上海飞广州",
            "查一下北京到深圳的航班",
        ],
        priority=100,
    ),
    IntentDefinition(
        name="set_alert",
        description="设置航班低价提醒",
        required_slots=["origin", "destination", "depart_date", "target_price"],
        optional_slots=["return_date", "constraints"],
        slot_schema={
            "origin": {"type": "string", "description": "出发城市中文名"},
            "destination": {"type": "string", "description": "目的地城市中文名"},
            "depart_date": {"type": "string", "description": "出发日期 YYYY-MM-DD"},
            "target_price": {"type": "integer", "description": "目标提醒价格"},
        },
        handler_name="set_alert",
        keywords=["提醒", "降价通知", "低价提醒", "蹲票", "低于", "降到"],
        examples=["北京到三亚低于500提醒我", "帮我蹲一下下周去成都的票"],
        priority=120,
    ),
    IntentDefinition(
        name="check_preference",
        description="查看用户出行偏好",
        required_slots=[],
        optional_slots=[],
        slot_schema={},
        handler_name="check_preference",
        keywords=["我的偏好", "出行偏好", "常去城市", "心理价位"],
        examples=["看看我的出行偏好", "我常去哪儿"],
        priority=110,
    ),
    IntentDefinition(
        name="update_preference",
        description="更新用户出行偏好",
        required_slots=["preference_value"],
        optional_slots=["preference_field"],
        slot_schema={
            "preference_field": {"type": "string", "description": "偏好字段名"},
            "preference_value": {"type": "string", "description": "新的偏好内容"},
        },
        handler_name="update_preference",
        keywords=["记住", "偏好改成", "以后帮我", "我喜欢", "我不想"],
        examples=["记住我喜欢早班机", "以后帮我避开红眼航班"],
        priority=115,
    ),
]


def default_intent(name: str) -> IntentDefinition | None:
    return next((item for item in DEFAULT_INTENTS if item.name == name), None)
