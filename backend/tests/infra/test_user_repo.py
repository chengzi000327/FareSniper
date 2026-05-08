from __future__ import annotations

import pytest

from backend.infrastructure.db.user_repo import allocate_anonymous, link_phone


@pytest.mark.asyncio
async def test_allocate_anonymous_unique(seeded_pg):
    a, b = await allocate_anonymous(), await allocate_anonymous()
    assert a != b
    assert a.startswith("anon_")


@pytest.mark.asyncio
async def test_link_phone_upgrades_user(seeded_pg):
    uid = await allocate_anonymous()
    upgraded = await link_phone(uid, "+8613800000000")
    assert upgraded.phone == "+8613800000000"
    assert upgraded.id == uid
