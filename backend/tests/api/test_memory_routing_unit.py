from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.api.memory import PatchReq, delete_memory_field, patch_memory


@pytest.mark.asyncio
async def test_preference_patch_updates_agent_preference_store() -> None:
    preference_writer = AsyncMock()
    generic_writer = AsyncMock()

    with (
        patch(
            "backend.api.memory.upsert_preference_override",
            new=preference_writer,
        ),
        patch("backend.api.memory.upsert_memory", new=generic_writer),
    ):
        response = await patch_memory(PatchReq(field="budget", value=850), uid="u1")

    assert response == {"ok": True}
    preference_writer.assert_awaited_once_with("u1", "budget", 850)
    generic_writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_preference_patch_stays_in_generic_memory_store() -> None:
    preference_writer = AsyncMock()
    generic_writer = AsyncMock()

    with (
        patch(
            "backend.api.memory.upsert_preference_override",
            new=preference_writer,
        ),
        patch("backend.api.memory.upsert_memory", new=generic_writer),
    ):
        await patch_memory(
            PatchReq(field="companion_profile", value={"kind": "cat"}),
            uid="u1",
        )

    generic_writer.assert_awaited_once_with(
        "u1", "companion_profile", {"kind": "cat"}, source="user"
    )
    preference_writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_preference_delete_clears_agent_and_manual_override() -> None:
    preference_clearer = AsyncMock()
    generic_clearer = AsyncMock()

    with (
        patch(
            "backend.api.memory.clear_preference_override",
            new=preference_clearer,
        ),
        patch("backend.api.memory.delete_field", new=generic_clearer),
    ):
        response = await delete_memory_field("preferred_airlines", uid="u1")

    assert response.status_code == 204
    preference_clearer.assert_awaited_once_with("u1", "preferred_airlines")
    generic_clearer.assert_not_awaited()

