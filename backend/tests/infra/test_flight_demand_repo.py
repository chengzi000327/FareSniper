from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from backend.application.contracts.flight_provider import FlightOffer

from backend.infrastructure.db.flight_demand_repo import (
    CollectorNodeRow,
    FlightSearchDemandRow,
    LeaseOwnershipError,
    claim_next,
    claim_due_demands,
    complete_job,
    enqueue_demand,
    fail_job,
    record_heartbeat,
)
from backend.infrastructure.db.flight_snapshot_repo import (
    read_provider_deals,
    upsert_provider_offers,
)


def _offer(*, price: int = 580) -> FlightOffer:
    return FlightOffer(
        data_provider="ctrip",
        seller_name="携程",
        flight_no="MU5106",
        airline="东方航空",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        depart_time="08:00",
        arrive_time="10:00",
        duration_minutes=120,
        currency="CNY",
        total_price=price,
        booking_url="https://flights.ctrip.com/booking/MU5106",
    )


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_and_raises_priority(seeded_pg):
    first_id = await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=10,
        source="recent_search",
    )
    second_id = await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=100,
        source="price_alert",
    )

    rows = await claim_due_demands(limit=10)

    assert first_id == second_id
    assert len(rows) == 1
    assert rows[0].priority == 100
    assert rows[0].source == "price_alert"


@pytest.mark.asyncio
async def test_claim_schedules_next_collection_one_hour_later(seeded_pg):
    await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=50,
        source="recent_search",
    )

    first_claim = await claim_due_demands(limit=10)
    second_claim = await claim_due_demands(limit=10)

    assert len(first_claim) == 1
    assert second_claim == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "depart_date",
    [
        "2099-02-30",
        "2099-8-01",
        "DATE_SECRET_SENTINEL hidden in a complete sentence",
    ],
)
async def test_enqueue_rejects_noncanonical_or_invalid_date(
    seeded_pg, depart_date
):
    with pytest.raises(ValueError, match="valid YYYY-MM-DD") as exc_info:
        await enqueue_demand(
            origin_code="BJS",
            destination_code="SHA",
            depart_date=depart_date,
            priority=10,
            source="recent_search",
        )

    assert depart_date not in str(exc_info.value)
    assert await claim_due_demands(limit=10) == []


@pytest.mark.asyncio
async def test_claim_next_uses_priority(seeded_pg):
    low_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "hot_route", 5
    )
    high_id = await enqueue_demand(
        "BJS", "SYX", "2099-08-01", "price_alert", 100
    )

    claimed = await claim_next("mac-1", lease_seconds=60)

    assert claimed is not None
    assert claimed.job_id == high_id
    assert claimed.job_id != low_id


@pytest.mark.asyncio
async def test_concurrent_claims_lease_a_job_only_once(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )

    first, second = await asyncio.gather(
        claim_next("mac-1", lease_seconds=60),
        claim_next("mac-2", lease_seconds=60),
    )

    claims = [job for job in (first, second) if job is not None]
    assert len(claims) == 1
    assert claims[0].job_id == job_id


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimed_and_attempt_count_increments(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    first = await claim_next("mac-1", lease_seconds=60)
    assert first is not None

    async with seeded_pg.begin() as connection:
        await connection.execute(
            update(FlightSearchDemandRow)
            .where(FlightSearchDemandRow.id == job_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    reclaimed = await claim_next("mac-2", lease_seconds=60)

    assert reclaimed is not None
    assert reclaimed.job_id == job_id
    assert reclaimed.node_id == "mac-2"
    assert reclaimed.attempts == 2


@pytest.mark.asyncio
async def test_fail_job_requires_owner_and_retry_is_idempotent(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    with pytest.raises(LeaseOwnershipError):
        await fail_job(job_id, "mac-2", "timeout", retry_at)

    assert await fail_job(job_id, "mac-1", "timeout", retry_at) is True
    assert await fail_job(job_id, "mac-1", "timeout", retry_at) is False
    assert await claim_next("mac-2", lease_seconds=60) is None

    async with seeded_pg.connect() as connection:
        row = (
            await connection.execute(
                select(
                    FlightSearchDemandRow.status,
                    FlightSearchDemandRow.attempts,
                    FlightSearchDemandRow.last_error,
                ).where(FlightSearchDemandRow.id == job_id)
            )
        ).one()
    assert row.status == "retry"
    assert row.attempts == 1
    assert row.last_error == "timeout"


@pytest.mark.asyncio
async def test_empty_and_failed_jobs_preserve_last_successful_snapshot(seeded_pg):
    await upsert_provider_offers("ctrip_snapshot", [_offer()], ttl_minutes=75)
    first_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    assert await complete_job(first_id, "mac-1", []) is True

    failed_job_id = await enqueue_demand(
        "BJS", "CAN", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    assert await fail_job(
        failed_job_id,
        "mac-1",
        "timeout",
        datetime.now(timezone.utc) + timedelta(minutes=5),
    ) is True

    rows, _, _ = await read_provider_deals(
        provider="ctrip_snapshot",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    assert rows
    assert rows[0]["lowest_price"] == 580


@pytest.mark.asyncio
async def test_complete_job_requires_owner_and_is_idempotent(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None

    with pytest.raises(LeaseOwnershipError):
        await complete_job(job_id, "mac-2", [_offer()])

    assert await complete_job(job_id, "mac-1", [_offer()]) is True
    assert await complete_job(job_id, "mac-1", [_offer(price=560)]) is False

    rows, _, _ = await read_provider_deals(
        provider="ctrip_snapshot",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    assert rows[0]["lowest_price"] == 580


@pytest.mark.asyncio
async def test_record_heartbeat_upserts_node_and_tracks_last_success(seeded_pg):
    await record_heartbeat("mac-1", "1.0.0", "ready")
    await record_heartbeat("mac-1", "1.1.0", "success")

    async with seeded_pg.connect() as connection:
        nodes = (
            await connection.execute(
                select(
                    CollectorNodeRow.version,
                    CollectorNodeRow.status,
                    CollectorNodeRow.last_success,
                )
            )
        ).all()

    assert len(nodes) == 1
    assert nodes[0].version == "1.1.0"
    assert nodes[0].status == "success"
    assert nodes[0].last_success is not None


@pytest.mark.asyncio
async def test_complete_job_records_node_success(seeded_pg):
    await record_heartbeat("mac-1", "1.0.0", "ready")
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None

    await complete_job(job_id, "mac-1", [_offer()])

    async with seeded_pg.connect() as connection:
        last_success = (
            await connection.execute(
                select(CollectorNodeRow.last_success).where(
                    CollectorNodeRow.node_id == "mac-1"
                )
            )
        ).scalar_one()
    assert last_success is not None
