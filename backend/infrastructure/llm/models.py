"""LangChain chat model factories."""

from __future__ import annotations

from backend.config import settings


def get_intent_model():
    return _build(settings.model_intent)


def get_judge_model():
    return _build(settings.model_judge)


def _build(model_name: str):
    if not settings.model_api_key or settings.model_api_key in ("", "mock"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                '{"origin":{"city":"北京","iata_code":"BJS"},'
                '"destination":{"city":"三亚","iata_code":"SYX"},'
                '"date_window":{"start_date":"2026-05-01","end_date":"2026-05-05"},'
                '"budget_cny":null,"constraints":[],"parse_failed":false}'
            ]
        )

    if "qwen" in model_name.lower():
        try:
            from langchain_community.chat_models.tongyi import ChatTongyi

            return ChatTongyi(model=model_name, dashscope_api_key=settings.model_api_key)
        except ImportError:
            pass

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        temperature=0.2,
    )
