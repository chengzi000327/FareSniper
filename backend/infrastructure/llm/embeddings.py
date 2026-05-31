from __future__ import annotations

import logging

from backend.config import settings

logger = logging.getLogger("faresniper.embeddings")

EMBED_MODEL = "text-embedding-v3"


def _async_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
    )


async def embed(text: str) -> list[float]:
    """Generate a text embedding, returning an empty vector when unavailable."""
    if not settings.model_api_key or not text.strip():
        return []
    if "api.deepseek.com" in settings.model_base_url:
        return []
    try:
        resp = await _async_client().embeddings.create(model=EMBED_MODEL, input=text)
        return list(resp.data[0].embedding)
    except Exception:
        logger.warning("embed_failed", exc_info=True)
        return []
