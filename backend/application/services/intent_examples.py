from __future__ import annotations

import math
from typing import TypedDict

from backend.application.contracts.intent_registry import IntentDefinition
from backend.infrastructure.db.intent_registry_repo import list_examples_with_embeddings
from backend.infrastructure.llm.embeddings import embed

FAST_PATH_THRESHOLD = 0.85


class FastIntentMatch(TypedDict):
    intent_name: str
    confidence: float
    example_text: str


async def fast_intent_match(text: str) -> FastIntentMatch | None:
    vector = await embed(text)
    if not vector:
        return None

    best: FastIntentMatch | None = None
    for row in await list_examples_with_embeddings():
        score = _cosine(vector, row.get("embedding") or [])
        if score <= FAST_PATH_THRESHOLD:
            continue
        if best is None or score > best["confidence"]:
            best = {
                "intent_name": str(row["intent_name"]),
                "confidence": score,
                "example_text": str(row.get("example_text") or ""),
            }
    return best


def render_intent_definitions(definitions: list[IntentDefinition]) -> str:
    if not definitions:
        return ""
    lines: list[str] = []
    for definition in definitions:
        required = ", ".join(definition.required_slots) or "无"
        optional = ", ".join(definition.optional_slots) or "无"
        examples = "；".join(definition.examples[:3]) or "无"
        lines.append(
            "\n".join(
                [
                    f"- {definition.name}: {definition.description}",
                    f"  handler: {definition.handler_name or '未配置'}",
                    f"  required_slots: {required}",
                    f"  optional_slots: {optional}",
                    f"  keywords: {', '.join(definition.keywords) or '无'}",
                    f"  examples: {examples}",
                ]
            )
        )
    return "\n".join(lines)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
