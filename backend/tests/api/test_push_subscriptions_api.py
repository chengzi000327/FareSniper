from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_save_push_subscription_bound_to_token_user(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    sub = {
        "endpoint": "https://push.example/u1",
        "keys": {"p256dh": "p256dh-test", "auth": "auth-test"},
    }
    r = await client.post(
        "/api/push/subscriptions",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"subscription": sub},
    )
    assert r.status_code == 204
