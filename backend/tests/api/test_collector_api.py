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
    CollectorOfferValidationError,
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


@pytest.mark.parametrize(
    "authorization",
    [
        "bearer collector-secret",
        "BEARER   collector-secret",
        "BeArEr\tcollector-secret",
        " \tBearer collector-secret\t ",
    ],
)
def test_collector_accepts_case_insensitive_bearer_with_horizontal_whitespace(
    configured_collector_token,
    authorization,
):
    collector_api.require_collector_token(authorization)


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic collector-secret",
        "Bearer",
        "Bearer secret extra",
        "Bearer\ncollector-secret",
        "Bearer \ncollector-secret",
        "Bearer abc=def",
        "Bearer 密钥",
    ],
)
def test_malformed_collector_auth_still_uses_compare_digest_and_fails_closed(
    monkeypatch,
    configured_collector_token,
    authorization,
):
    calls = []

    def fake_compare_digest(candidate: bytes, expected: bytes) -> bool:
        calls.append((candidate, expected))
        return candidate == expected

    monkeypatch.setattr(
        collector_api.secrets,
        "compare_digest",
        fake_compare_digest,
    )

    with pytest.raises(HTTPException) as exc_info:
        collector_api.require_collector_token(authorization)

    assert exc_info.value.status_code == 401
    assert calls == [(b"", b"collector-secret")]


@pytest.mark.parametrize("configured_token", ["abc=def", "密钥", "secret\nvalue"])
def test_collector_rejects_invalid_configured_token68(configured_token):
    original_token = settings.ctrip_collector_token
    object.__setattr__(settings, "ctrip_collector_token", configured_token)
    try:
        with pytest.raises(HTTPException) as exc_info:
            collector_api.require_collector_token(f"Bearer {configured_token}")
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
async def test_status_reports_sanitized_collector_and_scoped_job_state(
    monkeypatch, collector_client, collector_headers
):
    checked_at = datetime(2099, 7, 19, 12, 0, tzinfo=timezone.utc)
    calls = []

    async def read_collector_verification_status(**scope):
        calls.append(scope)
        return SimpleNamespace(
            collector_online=True,
            last_heartbeat_at=checked_at,
            last_success_at=checked_at,
            job_status="completed",
            job_updated_at=checked_at,
        )

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(
            read_collector_verification_status=(
                read_collector_verification_status
            )
        ),
        raising=False,
    )

    response = await collector_client.get(
        "/internal/collector/status",
        params={
            "origin_code": "AAT",
            "destination_code": "SYX",
            "depart_date": "2099-08-01",
        },
        headers=collector_headers,
    )

    assert response.status_code == 200
    assert calls == [
        {
            "origin_code": "AAT",
            "destination_code": "SYX",
            "depart_date": "2099-08-01",
            "heartbeat_timeout_seconds": 180,
        }
    ]
    assert response.json() == {
        "collector_online": True,
        "last_heartbeat_at": "2099-07-19T12:00:00Z",
        "last_success_at": "2099-07-19T12:00:00Z",
        "job_status": "completed",
        "job_updated_at": "2099-07-19T12:00:00Z",
    }
    assert "node_id" not in response.text


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
@pytest.mark.parametrize(
    ("booking_url", "expected_url"),
    [
        (
            "HTTPS://FLIGHTS.CTRIP.COM/online/list"
            "?infant=0&adult=2&depdate=2099-08-01&cabin=Y_1&child=1",
            "https://flights.ctrip.com/online/list"
            "?depdate=2099-08-01&cabin=Y_1&adult=2&child=1&infant=0",
        ),
        (
            "https://flights.ctrip.com/booking/MU5106?adult=1",
            "https://flights.ctrip.com/booking/MU5106?adult=1",
        ),
    ],
)
async def test_complete_normalizes_functional_ctrip_booking_query(
    monkeypatch,
    collector_client,
    collector_headers,
    booking_url,
    expected_url,
):
    calls = []

    async def complete_job(_job_id: str, _node_id: str, offers: list[object]):
        calls.append(offers)
        return True

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/complete",
        json={
            "node_id": "mac-1",
            "offers": [_wire_offer(booking_url=booking_url)],
        },
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert calls[0][0].booking_url == expected_url


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
        ({"booking_url": "https://flights%2Ectrip.com/booking"}, None),
        ({"booking_url": "https://user@flights.ctrip.com/booking"}, "user"),
        ({"booking_url": "https://flights.ctrip.com:443/booking"}, None),
        (
            {"booking_url": "https://flights.ctrip.com/booking#token-secret"},
            "token-secret",
        ),
        ({"booking_url": "https://flights.ctrip.com/booking\nnext"}, None),
        ({"booking_url": "https://flights.ctrip.com/booking%0Anext"}, None),
        (
            {
                "booking_url": (
                    "https://flights.ctrip.com/booking?cookie=cookie-secret"
                )
            },
            "cookie-secret",
        ),
        (
            {"booking_url": "https://flights.ctrip.com/booking?token=token-secret"},
            "token-secret",
        ),
        (
            {
                "booking_url": (
                    "https://flights.ctrip.com/booking?profile=profile-secret"
                )
            },
            "profile-secret",
        ),
        (
            {"booking_url": "https://flights.ctrip.com/booking?source=source-secret"},
            "source-secret",
        ),
        (
            {
                "booking_url": (
                    "https://flights.ctrip.com/booking?account=account-secret"
                )
            },
            "account-secret",
        ),
        (
            {
                "booking_url": (
                    "https://flights.ctrip.com/booking?%63ookie=encoded-secret"
                )
            },
            "encoded-secret",
        ),
        ({"booking_url": "https://flights.ctrip.com/booking?adult=1&adult=2"}, None),
        ({"booking_url": "https://flights.ctrip.com/booking?depdate=2099-02-30"}, None),
        ({"booking_url": "https://flights.ctrip.com/booking?depdate=2099-08-02"}, None),
        ({"booking_url": "https://flights.ctrip.com/booking?cabin=Y%20secret"}, None),
        ({"booking_url": "https://flights.ctrip.com/booking?adult=0"}, None),
        ({"booking_url": "https://flights.ctrip.com/" + "a" * 2050}, None),
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
    calls = []

    async def complete_job(*_args, **_kwargs):
        calls.append((_args, _kwargs))
        return True

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
    assert calls == []
    if secret:
        assert secret not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repository_error",
    [
        CollectorJobNotFoundError("job-existence-secret"),
        LeaseOwnershipError("cookie-and-browser-state-secret"),
        CollectorOfferValidationError("raw-offer-secret"),
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
async def test_complete_does_not_hide_unrelated_internal_value_error(
    monkeypatch,
    collector_client,
    collector_headers,
):
    async def complete_job(*_args, **_kwargs):
        raise ValueError("internal-programming-secret")

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(complete_job=complete_job),
    )

    with pytest.raises(ValueError, match="internal-programming-secret"):
        await collector_client.post(
            "/internal/collector/jobs/anonymous-job-1/complete",
            json={"node_id": "mac-1", "offers": [_wire_offer()]},
            headers=collector_headers,
        )


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
async def test_fail_accepts_rfc3339_offset_timestamp(
    monkeypatch,
    collector_client,
    collector_headers,
):
    calls = []

    async def fail_job(_job_id, _node_id, _error_code, retry_at):
        calls.append(retry_at)
        return True

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(fail_job=fail_job),
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/fail",
        json={
            "node_id": "mac-1",
            "error_code": "timeout",
            "retry_at": "2099-07-19T20:05:00.123456+08:00",
        },
        headers=collector_headers,
    )

    assert response.status_code == 204
    assert calls == [
        datetime.fromisoformat("2099-07-19T20:05:00.123456+08:00")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retry_at",
    [
        4_087_968_300,
        "2099-07-19T12:05:00",
        "2099-07-19 12:05:00Z",
        "2099-07-19T12:05Z",
        "2099-07-19T12:05:00.1234567Z",
        "2099-07-19T12:05:00profile-secret",
    ],
)
async def test_fail_rejects_non_rfc3339_or_naive_retry_at_without_echo(
    monkeypatch,
    collector_client,
    collector_headers,
    retry_at,
):
    calls = []

    async def fail_job(*_args, **_kwargs):
        calls.append((_args, _kwargs))
        return True

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(fail_job=fail_job),
    )

    response = await collector_client.post(
        "/internal/collector/jobs/anonymous-job-1/fail",
        json={
            "node_id": "mac-1",
            "error_code": "timeout",
            "retry_at": retry_at,
        },
        headers=collector_headers,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid collector request"}
    assert calls == []
    assert "profile-secret" not in response.text


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


@pytest.mark.asyncio
async def test_fail_does_not_hide_unrelated_internal_value_error(
    monkeypatch,
    collector_client,
    collector_headers,
):
    async def fail_job(*_args, **_kwargs):
        raise ValueError("internal-programming-secret")

    monkeypatch.setattr(
        collector_api,
        "flight_demand_repo",
        SimpleNamespace(fail_job=fail_job),
    )

    with pytest.raises(ValueError, match="internal-programming-secret"):
        await collector_client.post(
            "/internal/collector/jobs/anonymous-job-1/fail",
            json={
                "node_id": "mac-1",
                "error_code": "timeout",
                "retry_at": "2099-07-19T12:05:00Z",
            },
            headers=collector_headers,
        )
