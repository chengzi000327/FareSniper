import pytest
from backend.config import get_settings
from backend.infrastructure.llm.models import build_chat_model
from backend.infrastructure.observability.langfuse import attach_callback
import backend.infrastructure.observability.langfuse as lf_module


class _CapturedLangfuse:
    def __init__(self):
        self.last_metadata: dict = {}


@pytest.fixture
def captured_langfuse(monkeypatch):
    cap = _CapturedLangfuse()

    monkeypatch.setenv("MODEL_API_KEY", "")
    get_settings.cache_clear()

    def stub_make(run_id: str, *, model_version: str = ""):
        cap.last_metadata["model_version"] = model_version
        from langchain_core.callbacks.base import BaseCallbackHandler

        class _Noop(BaseCallbackHandler):
            pass

        return _Noop()

    monkeypatch.setattr(lf_module, "make_handler", stub_make)
    yield cap
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_attach_records_model_version(captured_langfuse):
    chat = build_chat_model(role="agent")
    chat = attach_callback(chat, run_id="r_test")
    await chat.ainvoke([{"role": "user", "content": "hi"}])
    assert captured_langfuse.last_metadata["model_version"] in {"qwen-plus", "deepseek-chat"}
