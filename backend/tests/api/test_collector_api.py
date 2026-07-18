from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from backend.api import collector as collector_api
from backend.config import settings
from backend.infrastructure.db.flight_demand_repo import (
    CollectorJob,
    CollectorJobNotFoundError,
    LeaseOwnershipError,
)
from backend.main import create_app


@pytest.fixture
def collector_headers() -> dict[str, str]:
    return {"Authorization": "Bearer collector-secret"}


@pytest.fixture
def configured_collector_token():
    field_existed = hasattr(settings, "ctrip_collector_token")
    original_token = getattr(settings, "ctrip_collector_token", None)
    object.__setattr__(settings, "ctrip_collector_token", "collector-secret")
    try:
        yield
    finally:
        if field_existed:
            object.__setattr__(
                settings, "ctrip_collector_token", original_token
            )
        else:
            object.__delattr__(settings, "ctrip_collector_token")


@pytest_asyncio.fixture
async def collector_client(configured_collector_token):
    transport = ASGITransport(app=create_app())
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


def _wire_offer(**overrides) -> dict:
    payload = {
        "data_provider": "ctrip_snapshot",
        "seller_name": "携程",
        "flight_no": "MU5106",
        "airline": "东方航空",
        "origin_city": "北京",
        "origin_code": "BJS",
        "destination_city": "上海",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "depart_time": "08:00",
        "arrive_time": "10:00",
        "duration_minutes": 120,
        "stops": 0,
        "cabin": "Y",
        "currency": "CNY",
        "display_price": 580,
        "booking_url": "https://flights.ctrip.com/booking/MU5106",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_collector_rejects_missing_or_wrong_token(
    configured_collector_token,
):
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing = await client.post(
            "/internal/collector/claim", json={"node_id": "mac-1"}
        )
        wrong = await client.post(
            "/internal/collector/claim",
            json={"node_id": "mac-1"},
            headers={"Authorization": "Bearer wrong"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert "collector-secret" not in missing.text + wrong.text


@pytest.mark.asyncio
async def test_collector_rejects_all_tokens_when_unconfigured():
    transport = ASGITransport(app=create_app())
    field_existed = hasattr(settings, "ctrip_collector_token")
    original_token = getattr(settings, "ctrip_collector_token", None)
    object.__setattr__(settings, "ctrip_collector_token", "")
    try:
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/internal/collector/claim",
                json={"node_id": "mac-1"},
                headers={"Authorization": "Bearer any-token"},
            )
    finally:
        if field_existed:
            object.__setattr__(
                settings, "ctrip_collector_token", original_token
            )
        else:
            object.__delattr__(settings, "ctrip_collector_token")

    assert response.status_code == 401


def test_collector_rejects_matching_whitespace_only_configured_token():
    original_token = settings.ctrip_collector_token
    object.__setattr__(settings, "ctrip_collector_token", "   ")
    try:
        with pytest.raises(HTTPException) as exc_info:
            collector_api.require_collector_token("Bearer    ")
    finally:
        object.__setattr__(settings, "ctrip_collector_token", original_token)

    assert getattr(exc_info.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_collector_router_has_no_public_api_prefix(
    configured_collector_token,
):
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/internal/collector/claim",
            json={"node_id": "mac-1"},
            headers={"Authorization": "Bearer collector-secret"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_collector_auth_uses_compare_digest(
    monkeypatch, collector_client, collector_headers
):
    calls: list[tuple[bytes, bytes]] = []

    def fake_compare_digest(candidate: bytes, expected: bytes) -> bool:
        calls.append((candidate, expected))
        return candidate == expected

    async def claim_next(_node_id: str, *, lease_seconds: int):
        assert lease_seconds == 180
        return None

    monkeypatch.setattr(collector_api.secrets, "compare_digest", fake_compare_digest)
    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(claim_next=claim_next),
    )

    await collector_client.post(
        "/internal/collector/claim",
        json={"node_id": "mac-1"},
        headers=collector_headers,
    )

    assert calls == [(b"collector-secret", b"collector-secret")]


@pytest.mark.asyncio
async def test_claim_returns_one_repository_leased_job(
    monkeypatch, collector_client, collector_headers
):
    lease_expires_at = datetime(2099, 7, 19, 12, 0, tzinfo=timezone.utc)
    claimed_job = CollectorJob(
        job_id="anonymous-job-1",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        source="recent_search",
        priority=50,
        attempts=1,
        node_id="mac-1",
        lease_expires_at=lease_expires_at,
    )
    calls: list[tuple[str, int]] = []

    async def claim_next(node_id: str, lease_seconds: int):
        calls.append((node_id, lease_seconds))
        return claimed_job

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(claim_next=claim_next),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/claim",
        json={"node_id": "mac-1"},
        headers=collector_headers,
    )

    assert response.status_code == 200
    assert calls == [("mac-1", 180)]
    assert response.json() == {
        "job": {
            "job_id": "anonymous-job-1",
            "origin_code": "BJS",
            "destination_code": "SHA",
            "depart_date": "2099-08-01",
            "source": "recent_search",
            "priority": 50,
            "attempts": 1,
            "lease_expires_at": "2099-07-19T12:00:00Z",
        }
    }


@pytest.mark.asyncio
async def test_claim_returns_null_when_no_job_is_available(
    monkeypatch, collector_client, collector_headers
):
    async def claim_next(_node_id: str, *, lease_seconds: int):
        assert lease_seconds == 180
        return None

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(claim_next=claim_next),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/claim",
        json={"node_id": "mac-1"},
        headers=collector_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"job": None}


@pytest.mark.asyncio
async def test_claim_uses_collector_claim_trace_wrapper(
    monkeypatch, collector_client, collector_headers
):
    trace_calls = []

    async def claim_next(_node_id: str, *, lease_seconds: int):
        assert lease_seconds == 180
        return None

    async def trace_collector_claim(operation):
        trace_calls.append("claim")
        return await operation()

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(claim_next=claim_next),
    )
    monkeypatch.setattr(
        collector_api,
        "trace_collector_claim",
        trace_collector_claim,
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/claim",
        json={"node_id": "mac-1"},
        headers=collector_headers,
    )

    assert response.status_code == 200
    assert trace_calls == ["claim"]


@pytest.mark.asyncio
async def test_heartbeat_records_node_through_repository(
    monkeypatch, collector_client, collector_headers
):
    calls: list[tuple[str, str, str]] = []

    async def record_heartbeat(node_id: str, version: str, status: str):
        calls.append((node_id, version, status))

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(record_heartbeat=record_heartbeat),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/heartbeat",
        json={"node_id": "mac-1", "version": "1.2.3", "status": "idle"},
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert calls == [("mac-1", "1.2.3", "idle")]


@pytest.mark.asyncio
async def test_complete_maps_snapshot_wire_identity_to_trusted_ctrip_offer(
    monkeypatch, collector_client, collector_headers
):
    calls = []

    async def complete_job(job_id: str, node_id: str, offers: list[object]):
        calls.append((job_id, node_id, offers))
        return True

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/complete",
        json={"node_id": "mac-1", "offers": [_wire_offer()]},
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert len(calls) == 1
    job_id, node_id, offers = calls[0]
    assert (job_id, node_id) == ("anonymous-job-1", "mac-1")
    assert len(offers) == 1
    offer = offers[0]
    assert offer.data_provider == "ctrip"
    assert offer.seller_name == "携程"
    assert offer.total_price == 580
    assert offer.base_price is None
    assert offer.currency == "CNY"
    assert offer.origin_code == "BJS"
    assert offer.destination_code == "SHA"
    assert offer.depart_date == "2099-08-01"


@pytest.mark.asyncio
async def test_complete_uses_collector_ingest_trace_wrapper(
    monkeypatch, collector_client, collector_headers
):
    trace_calls = []

    async def complete_job(_job_id: str, _node_id: str, _offers: list[object]):
        return True

    async def trace_collector_ingest(job_id, result_count, operation):
        trace_calls.append((job_id, result_count))
        return await operation()

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
    )
    monkeypatch.setattr(
        collector_api,
        "trace_collector_ingest",
        trace_collector_ingest,
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/complete",
        json={"node_id": "mac-1", "offers": [_wire_offer()]},
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert trace_calls == [("anonymous-job-1", 1)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "secret"),
    [
        ({"display_price": 0}, None),
        ({"display_price": -1}, None),
        ({"display_price": True}, None),
        ({"display_price": 580.0}, None),
        ({"display_price": "580"}, "580"),
        ({"currency": "USD"}, "USD"),
        ({"data_provider": "ctrip"}, "ctrip"),
        ({"seller_name": "Trip.com"}, "Trip.com"),
        ({"booking_url": "http://flights.ctrip.com/booking"}, None),
        ({"booking_url": "https://flights.ctrip.com.evil.test/booking"}, "evil.test"),
        ({"raw_payload": {"cookie": "cookie-secret"}}, "cookie-secret"),
        ({"raw_reference": "browser-state-secret"}, "browser-state-secret"),
    ],
)
async def test_complete_rejects_untrusted_offer_fields_without_echoing_input(
    monkeypatch,
    collector_client,
    collector_headers,
    overrides,
    secret,
):
    async def complete_job(*_args, **_kwargs):
        raise AssertionError("invalid offers must not reach the repository")

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/complete",
        json={"node_id": "mac-1", "offers": [_wire_offer(**overrides)]},
        headers=collector_headers,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid collector request"}
    if secret:
        assert secret not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repository_error",
    [
        CollectorJobNotFoundError("job-existence-secret"),
        LeaseOwnershipError("cookie-and-browser-state-secret"),
        ValueError("raw-offer-secret"),
    ],
)
async def test_complete_repository_rejections_are_indistinguishable(
    monkeypatch,
    collector_client,
    collector_headers,
    repository_error,
):
    async def complete_job(*_args, **_kwargs):
        raise repository_error

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/complete",
        json={"node_id": "mac-1", "offers": [_wire_offer()]},
        headers=collector_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "job unavailable"}
    assert "secret" not in response.text


@pytest.mark.asyncio
async def test_fail_delegates_ownership_check_to_repository(
    monkeypatch, collector_client, collector_headers
):
    calls = []

    async def fail_job(job_id, node_id, error_code, retry_at):
        calls.append((job_id, node_id, error_code, retry_at))
        return True

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(fail_job=fail_job),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/fail",
        json={
            "node_id": "mac-1",
            "error_code": "timeout",
            "retry_at": "2099-07-19T12:05:00Z",
        },
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert calls[0][:3] == ("anonymous-job-1", "mac-1", "timeout")
    assert calls[0][3] == datetime(
        2099, 7, 19, 12, 5, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_fail_hides_job_existence_and_ownership_details(
    monkeypatch, collector_client, collector_headers
):
    async def fail_job(*_args, **_kwargs):
        raise CollectorJobNotFoundError("job-existence-secret")

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(fail_job=fail_job),
        raising=False,
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/fail",
        json={
            "node_id": "mac-1",
            "error_code": "timeout",
            "retry_at": "2099-07-19T12:05:00Z",
        },
        headers=collector_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "job unavailable"}
    assert "job-existence-secret" not in response.text
