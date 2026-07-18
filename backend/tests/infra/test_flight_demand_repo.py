from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, update

from backend.application.contracts.flight_provider import FlightOffer
import backend.infrastructure.db.flight_snapshot_repo as snapshot_repo

from backend.infrastructure.db.flight_demand_repo import (
    CollectorNodeRow,
    CollectorOfferValidationError,
    FlightSearchDemandRow,
    LeaseOwnershipError,
    claim_next,
    complete_job,
    enqueue_demand,
    fail_job,
    read_collector_verification_status,
    record_heartbeat,
)
from backend.infrastructure.db.flight_snapshot_repo import (
    PlatformPriceSnapshot,
    read_provider_deals,
    upsert_provider_offers,
)


def _offer(
    *,
    price: int = 580,
    data_provider: str = "ctrip",
    seller_name: str = "携程",
    origin_code: str = "BJS",
    destination_code: str = "SHA",
    depart_date: str = "2099-08-01",
    booking_url: str | None = "https://flights.ctrip.com/booking/MU5106",
) -> FlightOffer:
    return FlightOffer(
        data_provider=data_provider,
        seller_name=seller_name,
        flight_no="MU5106",
        airline="东方航空",
        origin_city="北京",
        origin_code=origin_code,
        origin_airport_code="PEK" if origin_code == "BJS" else origin_code,
        destination_city="上海",
        destination_code=destination_code,
        destination_airport_code=(
            "SHA" if destination_code == "SHA" else destination_code
        ),
        depart_date=depart_date,
        depart_time="08:00",
        arrive_time="10:00",
        duration_minutes=120,
        currency="CNY",
        total_price=price,
        booking_url=booking_url,
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

    claimed = await claim_next("mac-1", lease_seconds=60)

    assert first_id == second_id
    assert claimed is not None
    assert claimed.priority == 100
    assert claimed.source == "price_alert"


@pytest.mark.asyncio
async def test_lower_priority_collision_preserves_higher_priority_provenance(
    seeded_pg,
):
    job_id = await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=100,
        source="price_alert",
    )
    duplicate_id = await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=5,
        source="hot_route",
    )

    claimed = await claim_next("mac-1", lease_seconds=60)

    assert duplicate_id == job_id
    assert claimed is not None
    assert claimed.priority == 100
    assert claimed.source == "price_alert"


@pytest.mark.asyncio
async def test_enqueue_rejects_unapproved_source(seeded_pg):
    with pytest.raises(ValueError, match="approved demand source"):
        await enqueue_demand(
            "BJS", "SHA", "2099-08-01", "browser_worker", 50
        )

    assert await claim_next("mac-1", lease_seconds=60) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "depart_date",
    [
        datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
        "2000-01-01",
    ],
)
async def test_enqueue_rejects_non_future_shanghai_date(
    seeded_pg,
    depart_date,
):
    with pytest.raises(ValueError, match="future depart_date"):
        await enqueue_demand(
            "BJS", "SHA", depart_date, "recent_search", 50
        )

    assert await claim_next("mac-1", lease_seconds=60) is None


@pytest.mark.asyncio
async def test_claim_next_deactivates_legacy_same_day_demand(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    async with seeded_pg.begin() as connection:
        await connection.execute(
            update(FlightSearchDemandRow)
            .where(FlightSearchDemandRow.id == job_id)
            .values(depart_date=today)
        )

    assert await claim_next("mac-1", lease_seconds=60) is None
    async with seeded_pg.connect() as connection:
        active = (
            await connection.execute(
                select(FlightSearchDemandRow.active).where(
                    FlightSearchDemandRow.id == job_id
                )
            )
        ).scalar_one()
    assert active is False


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
    assert await claim_next("mac-1", lease_seconds=60) is None


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
    with pytest.raises(CollectorOfferValidationError, match="at least one"):
        await complete_job(first_id, "mac-1", [])
    assert await fail_job(
        first_id,
        "mac-1",
        "empty",
        datetime.now(timezone.utc) + timedelta(minutes=5),
    ) is True

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
async def test_complete_job_rejects_offer_without_ctrip_booking_url(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None

    with pytest.raises(CollectorOfferValidationError, match="booking URL"):
        await complete_job(job_id, "mac-1", [_offer(booking_url=None)])

    async with seeded_pg.connect() as connection:
        status = (
            await connection.execute(
                select(FlightSearchDemandRow.status).where(
                    FlightSearchDemandRow.id == job_id
                )
            )
        ).scalar_one()
    assert status == "leased"


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
async def test_reenqueue_completed_hourly_demand_creates_a_new_claim(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    first = await claim_next("mac-1", lease_seconds=60)
    assert first is not None
    await complete_job(job_id, "mac-1", [_offer()])

    duplicate_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    second = await claim_next("mac-1", lease_seconds=60)

    assert duplicate_id == job_id
    assert second is not None
    assert second.job_id == job_id
    assert second.attempts == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "offer",
    [
        _offer(origin_code="CAN"),
        _offer(destination_code="SYX"),
        _offer(depart_date="2099-08-02"),
    ],
)
async def test_completed_job_replay_still_validates_exact_scope(
    seeded_pg,
    offer,
):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    assert await complete_job(job_id, "mac-1", [_offer()]) is True

    with pytest.raises(CollectorOfferValidationError, match="leased job"):
        await complete_job(job_id, "mac-1", [offer])


@pytest.mark.asyncio
async def test_completed_job_replay_still_validates_ctrip_identity(seeded_pg):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    assert await complete_job(job_id, "mac-1", [_offer()]) is True

    with pytest.raises(CollectorOfferValidationError, match="Ctrip identity"):
        await complete_job(
            job_id,
            "mac-1",
            [_offer(data_provider="ctrip_snapshot")],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data_provider", "seller_name"),
    [("serpapi", "携程"), ("ctrip", "Other Seller")],
)
async def test_complete_job_rejects_non_ctrip_offer_identity(
    seeded_pg,
    data_provider,
    seller_name,
):
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None

    with pytest.raises(ValueError, match="Ctrip identity"):
        await complete_job(
            job_id,
            "mac-1",
            [
                _offer(
                    data_provider=data_provider,
                    seller_name=seller_name,
                )
            ],
        )

    rows, _, _ = await read_provider_deals(
        "ctrip_snapshot", "BJS", "SHA", "2099-08-01"
    )
    assert rows == []
    async with seeded_pg.connect() as connection:
        status = (
            await connection.execute(
                select(FlightSearchDemandRow.status).where(
                    FlightSearchDemandRow.id == job_id
                )
            )
        ).scalar_one()
    assert status == "leased"


@pytest.mark.asyncio
async def test_snapshot_failure_rolls_back_job_and_existing_snapshot(
    seeded_pg,
    monkeypatch,
):
    await upsert_provider_offers("ctrip_snapshot", [_offer()], ttl_minutes=75)
    job_id = await enqueue_demand(
        "BJS", "SHA", "2099-08-01", "recent_search", 50
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None

    async def fail_after_snapshot_write(
        session,
        provider,
        offers,
        ttl_minutes,
        *,
        origin_airport_code=None,
        destination_airport_code=None,
    ):
        assert origin_airport_code is None
        assert destination_airport_code is None
        await session.execute(
            update(PlatformPriceSnapshot)
            .where(PlatformPriceSnapshot.data_provider == "ctrip_snapshot")
            .values(price=1)
        )
        raise RuntimeError("injected snapshot failure")

    monkeypatch.setattr(
        snapshot_repo,
        "_upsert_provider_offers_in_session",
        fail_after_snapshot_write,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="injected snapshot failure"):
        await complete_job(job_id, "mac-1", [_offer(price=560)])

    async with seeded_pg.connect() as connection:
        job = (
            await connection.execute(
                select(
                    FlightSearchDemandRow.status,
                    FlightSearchDemandRow.lease_owner,
                    FlightSearchDemandRow.lease_expires_at,
                ).where(FlightSearchDemandRow.id == job_id)
            )
        ).one()
        price = (
            await connection.execute(
                select(PlatformPriceSnapshot.price).where(
                    PlatformPriceSnapshot.data_provider == "ctrip_snapshot"
                )
            )
        ).scalar_one()

    assert job.status == "leased"
    assert job.lease_owner == "mac-1"
    assert job.lease_expires_at is not None
    assert price == 580


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


@pytest.mark.asyncio
async def test_verification_status_reports_exact_scoped_ingestion(seeded_pg):
    await record_heartbeat("mac-1", "1.0.0", "ready")
    job_id = await enqueue_demand(
        "BJS",
        "SHA",
        "2099-08-01",
        "recent_search",
        50,
        origin_airport_code="PEK",
        destination_airport_code="SHA",
    )
    assert await claim_next("mac-1", lease_seconds=60) is not None
    await complete_job(job_id, "mac-1", [_offer()])

    exact = await read_collector_verification_status(
        origin_code="BJS",
        origin_airport_code="PEK",
        destination_code="SHA",
        destination_airport_code="SHA",
        depart_date="2099-08-01",
        heartbeat_timeout_seconds=180,
    )
    other_airport = await read_collector_verification_status(
        origin_code="BJS",
        origin_airport_code="PKX",
        destination_code="SHA",
        destination_airport_code="SHA",
        depart_date="2099-08-01",
        heartbeat_timeout_seconds=180,
    )

    assert exact.job_status == "completed"
    assert exact.job_attempts == 1
    assert exact.snapshot_observed_at is not None
    assert other_airport.job_status == "missing"
    assert other_airport.job_attempts == 0
    assert other_airport.snapshot_observed_at is None
