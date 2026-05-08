from __future__ import annotations

from langchain_core.callbacks.base import BaseCallbackHandler

from backend.config import get_settings


def make_handler(run_id: str, *, model_version: str = "") -> BaseCallbackHandler:
    s = get_settings()
    if s.langfuse_public_key and s.langfuse_secret_key:
        try:
            from langfuse.callback import CallbackHandler

            return CallbackHandler(
                public_key=s.langfuse_public_key,
                secret_key=s.langfuse_secret_key,
                host=s.langfuse_host,
                session_id=run_id,
                metadata={"model_version": model_version},
            )
        except Exception:
            pass

    class _Noop(BaseCallbackHandler):
        pass

    return _Noop()


def attach_callback(chat, run_id: str):
    s = get_settings()
    model_version = (
        getattr(chat, "model", None)
        or getattr(chat, "model_name", None)
        or s.model_agent
    )
    handler = make_handler(run_id, model_version=model_version)
    return chat.with_config({"callbacks": [handler]})
