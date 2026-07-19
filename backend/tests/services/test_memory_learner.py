from __future__ import annotations

from typing import Any

import pytest

from backend.services.memory_learner import learn_from_query_history


class _Session:
    commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self) -> None:
        self.commits += 1


class _FakeLongTermMemory:
    recent: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    def __init__(self, _session) -> None:
        pass

    async def get_recent_queries(self, _user_id: str, limit: int = 30):
        assert limit == 30
        return self.recent

    async def get_preferences(self, _user_id: str):
        return {
            "frequent_cities": [],
            "preferred_airlines": [],
            "constraints": [],
            "travel_scenes": [],
            "budget": None,
        }

    async def upsert_preferences(self, _user_id: str, updates: dict[str, Any]):
        self.updates.append(updates)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("destination", "expected_city"),
    [
        ({"city": "三亚", "iata_code": "SYX", "confidence": 1.0}, "三亚"),
        ("上海", "上海"),
    ],
)
async def test_query_history_learns_hashable_city_from_destination_shapes(
    destination, expected_city, monkeypatch
):
    _FakeLongTermMemory.recent = [
        {"intent": {"destination": destination}} for _ in range(3)
    ]
    _FakeLongTermMemory.updates = []
    monkeypatch.setattr(
        "backend.memory.long_term.LongTermMemory", _FakeLongTermMemory
    )

    await learn_from_query_history("u1", _Session)

    assert _FakeLongTermMemory.updates == [
        {"frequent_cities": [expected_city]}
    ]
