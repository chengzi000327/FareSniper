"""Runtime loader and matcher for dynamic intent definitions."""

from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher

import redis.asyncio as redis

from backend.application.contracts.intent import SlotBundle
from backend.application.contracts.intent_registry import IntentDefinition, IntentMatch
from backend.application.services.default_intents import DEFAULT_INTENTS
from backend.config import settings

logger = logging.getLogger("faresniper.intent_registry")

CACHE_KEY = "intent_registry:active"
CACHE_TTL_SECONDS = 60

# Minimum confidence for a fresh intent to be treated as an unambiguous,
# high-signal match (keyword or exact-example hit) that may break session stickiness.
STRONG_MATCH_THRESHOLD = 0.9


async def load_intent_registry() -> list[IntentDefinition]:
    cached = await _load_from_cache()
    if cached:
        return cached

    db_defs = await _load_from_db()
    definitions = db_defs or DEFAULT_INTENTS
    await _save_to_cache(definitions)
    return definitions


async def invalidate_intent_registry_cache() -> None:
    if not settings.redis_url:
        return
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.delete(CACHE_KEY)
    finally:
        await client.aclose()


def _best_content_match(
    text: str, definitions: list[IntentDefinition]
) -> IntentMatch | None:
    candidates: list[IntentMatch] = []
    for definition in definitions:
        if not definition.is_active:
            continue
        score, matched_by = _score_intent(text, definition)
        if score > 0:
            candidates.append(
                IntentMatch(
                    intent_name=definition.name,
                    confidence=score,
                    matched_by=matched_by,
                    definition=definition,
                )
            )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item.confidence, item.definition.priority),
        reverse=True,
    )
    return candidates[0]


def match_intent(
    text: str,
    definitions: list[IntentDefinition],
    accumulated: SlotBundle | None = None,
) -> IntentMatch | None:
    normalized = (text or "").strip()
    fresh = _best_content_match(normalized, definitions)

    if accumulated and accumulated.intent:
        session_def = find_intent_definition(definitions, accumulated.intent)
        if session_def:
            # A high-confidence fresh match (keyword / exact-example hit) on a
            # *different* intent breaks session stickiness — the user switched goals.
            # 新一轮命中关键词/例句的高置信、不同意图 → 切换，破除粘滞。
            if fresh and fresh.intent_name != accumulated.intent and fresh.confidence >= STRONG_MATCH_THRESHOLD:
                return fresh
            return IntentMatch(
                intent_name=session_def.name,
                confidence=0.9,
                matched_by="session",
                definition=session_def,
            )

    return fresh


def find_intent_definition(
    definitions: list[IntentDefinition], name: str | None
) -> IntentDefinition | None:
    if not name:
        return None
    return next((item for item in definitions if item.name == name), None)


def required_slots_for(
    definitions: list[IntentDefinition], intent_name: str | None
) -> list[str]:
    definition = find_intent_definition(definitions, intent_name)
    if definition:
        return definition.required_slots
    fallback = find_intent_definition(DEFAULT_INTENTS, intent_name)
    return fallback.required_slots if fallback else []


async def _load_from_cache() -> list[IntentDefinition]:
    if not settings.redis_url:
        return []
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = await client.get(CACHE_KEY)
        if not raw:
            return []
        payload = json.loads(raw)
        return [IntentDefinition(**item) for item in payload]
    except Exception:
        logger.exception("intent_registry_cache_load_failed")
        return []
    finally:
        await client.aclose()


async def _save_to_cache(definitions: list[IntentDefinition]) -> None:
    if not settings.redis_url:
        return
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        payload = json.dumps([item.model_dump() for item in definitions])
        await client.setex(CACHE_KEY, CACHE_TTL_SECONDS, payload)
    except Exception:
        logger.exception("intent_registry_cache_save_failed")
    finally:
        await client.aclose()


async def _load_from_db() -> list[IntentDefinition]:
    if not settings.database_url:
        return []
    try:
        from backend.infrastructure.db.intent_registry_repo import list_active_intents

        return await list_active_intents()
    except Exception:
        logger.exception("intent_registry_db_load_failed")
        return []


def _score_intent(text: str, definition: IntentDefinition) -> tuple[float, str]:
    for keyword in definition.keywords:
        if keyword and keyword in text:
            return 0.95, f"keyword:{keyword}"

    best_example = 0.0
    for example in definition.examples:
        if example and example in text:
            return 0.9, "example:contains"
        best_example = max(best_example, SequenceMatcher(None, text, example).ratio())
    if best_example >= 0.68:
        return round(best_example, 2), "example:fuzzy"

    return 0.0, ""
