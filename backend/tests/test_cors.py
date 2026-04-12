import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_preflight(client: AsyncClient) -> None:
    response = await client.options(
        "/api/search",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" in response.headers
