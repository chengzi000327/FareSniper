"""LangChain chat model factories."""

from __future__ import annotations

from backend.config import get_settings


def get_intent_model():
    return _build(get_settings().model_intent)


def get_judge_model():
    return _build(get_settings().model_judge)


def build_chat_model(role: str = "agent"):
    """Unified factory for all roles: agent, intent, judge."""
    s = get_settings()
    model_name = s.model_agent if role == "agent" else s.model_judge
    return _build(model_name)


def _build(model_name: str):
    s = get_settings()
    if not s.model_api_key or s.model_api_key in ("", "mock"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                '{"origin":{"city":"北京","iata_code":"BJS"},'
                '"destination":{"city":"三亚","iata_code":"SYX"},'
                '"date_window":{"start_date":"2026-05-01","end_date":"2026-05-05"},'
                '"budget_cny":null,"constraints":[],"parse_failed":false}'
            ]
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=s.model_api_key,
        base_url=s.model_base_url,
        temperature=0.2,
    )
