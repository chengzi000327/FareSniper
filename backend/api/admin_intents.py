from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api._deps import current_user_id
from backend.application.contracts.intent_registry import IntentDefinition
from backend.application.services.default_intents import DEFAULT_INTENTS
from backend.application.services.intent_registry import (
    invalidate_intent_registry_cache,
    load_intent_registry,
)
from backend.infrastructure.llm.embeddings import embed
from backend.infrastructure.db.intent_registry_repo import (
    insert_example,
    list_intents,
    replace_examples,
    set_example_embedding,
    upsert_intent,
)

router = APIRouter(prefix="/admin/intents", tags=["admin-intents"])


@router.get("", response_model=list[IntentDefinition])
async def get_intents(_uid: str = Depends(current_user_id)) -> list[IntentDefinition]:
    rows = await list_intents()
    return rows or DEFAULT_INTENTS


@router.get("/active", response_model=list[IntentDefinition])
async def get_active_intents(
    _uid: str = Depends(current_user_id),
) -> list[IntentDefinition]:
    return await load_intent_registry()


@router.post("", response_model=IntentDefinition)
async def save_intent(
    body: IntentDefinition,
    _uid: str = Depends(current_user_id),
) -> IntentDefinition:
    saved = await upsert_intent(body)
    if body.examples:
        await _replace_examples_with_embeddings(body.name, body.examples)
    await invalidate_intent_registry_cache()
    return saved


@router.post("/{intent_name}/examples")
async def save_examples(
    intent_name: str,
    examples: list[str],
    _uid: str = Depends(current_user_id),
) -> dict:
    await _replace_examples_with_embeddings(intent_name, examples)
    await invalidate_intent_registry_cache()
    return {"ok": True, "intent_name": intent_name, "count": len(examples)}


@router.post("/cache/invalidate")
async def invalidate_cache(_uid: str = Depends(current_user_id)) -> dict:
    await invalidate_intent_registry_cache()
    return {"ok": True}


async def _replace_examples_with_embeddings(
    intent_name: str,
    examples: list[str],
) -> None:
    await replace_examples(intent_name, [])
    for example in examples:
        await _add_example_with_embedding(intent_name, example)


async def _add_example_with_embedding(intent_name: str, example_text: str) -> int:
    example_id = await insert_example(intent_name, example_text)
    vector = await embed(example_text)
    if vector:
        await set_example_embedding(example_id, vector)
    return example_id
