"""In-process Langfuse stand-in for tests that don't need network calls.

Tests can monkeypatch ``backend.infrastructure.observability.langfuse``
to point at this object once that production module exists. Until then
the fixture simply yields a fresh instance, leaving callers free to
exercise the surface (``score``, ``get_prompt``, ``last_metadata``)
without triggering real Langfuse SDK behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _StubPrompt:
    prompt: str = "stub"


class CapturedLangfuse:
    def __init__(self) -> None:
        self.scores: list[dict] = []
        self.last_metadata: dict = {}

    def score(self, *, name: str, value: float) -> None:
        self.scores.append({"name": name, "value": value})

    def get_prompt(self, _name: str) -> _StubPrompt:
        return _StubPrompt()
