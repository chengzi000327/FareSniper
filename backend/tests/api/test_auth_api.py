"""TG-12 Task 6: OTP login flow."""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient


def enable_test_sms(monkeypatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "sms_provider", "aliyun")
    monkeypatch.setattr(settings, "sms_aliyun_access_key_id", "test-key")


def test_phone_login_available_requires_provider_credentials(monkeypatch):
    from backend.api.auth import phone_login_available
    from backend.config import settings

    monkeypatch.setattr(settings, "sms_provider", "aliyun")
    monkeypatch.setattr(settings, "sms_aliyun_access_key_id", "")
    assert phone_login_available() is False

    monkeypatch.setattr(settings, "sms_aliyun_access_key_id", "test-key")
    assert phone_login_available() is True


@pytest.mark.asyncio
async def test_auth_status_reports_unconfigured_sms(
    client: AsyncClient, monkeypatch
):
    from backend.config import settings

    monkeypatch.setattr(settings, "sms_provider", "aliyun")
    monkeypatch.setattr(settings, "sms_aliyun_access_key_id", "")

    response = await client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {"phone_login_available": False}


@pytest.mark.asyncio
async def test_otp_request_and_verify(
    seeded_pg, fake_redis, fake_sms, client: AsyncClient, monkeypatch
):
    import backend.infrastructure.redis.session_store as ss

    enable_test_sms(monkeypatch)
    monkeypatch.setattr(ss, "_pool", fake_redis)

    r = await client.post("/api/auth/otp", json={"phone": "+8613800000000"})
    assert r.status_code == 204
    code = fake_sms.last_code_for("+8613800000000")
    r2 = await client.post(
        "/api/auth/verify", json={"phone": "+8613800000000", "code": code}
    )
    assert r2.status_code == 200
    assert r2.json()["access_token"]


@pytest.mark.asyncio
async def test_same_phone_returns_same_user_id(
    seeded_pg, fake_redis, fake_sms, client: AsyncClient, monkeypatch
):
    import backend.infrastructure.redis.session_store as ss

    enable_test_sms(monkeypatch)
    monkeypatch.setattr(ss, "_pool", fake_redis)

    await client.post("/api/auth/otp", json={"phone": "+8613800000001"})
    code1 = fake_sms.last_code_for("+8613800000001")
    u1 = (
        await client.post(
            "/api/auth/verify", json={"phone": "+8613800000001", "code": code1}
        )
    ).json()["user_id"]

    await client.post("/api/auth/otp", json={"phone": "+8613800000001"})
    code2 = fake_sms.last_code_for("+8613800000001")
    u2 = (
        await client.post(
            "/api/auth/verify", json={"phone": "+8613800000001", "code": code2}
        )
    ).json()["user_id"]

    assert u1 == u2
