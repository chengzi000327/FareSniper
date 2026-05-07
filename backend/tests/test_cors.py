from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_cors_preflight_includes_allow_origin_header(client: AsyncClient) -> None:
    response = await client.options(
        "/api/search",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" in response.headers


def test_cors_echoes_configured_frontend_origin():
    """Tightened CORS reflects only allow-listed origins, not '*'."""
    with TestClient(app) as tc:
        response = tc.options(
            "/health",
            headers={
                "Origin": "https://faresniper.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://faresniper.app"
        )


def test_cors_rejects_unlisted_origin():
    """Origins not in settings.cors_origins must not be echoed."""
    with TestClient(app) as tc:
        response = tc.options(
            "/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            response.headers.get("access-control-allow-origin")
            != "https://evil.example.com"
        )
