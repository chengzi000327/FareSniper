from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import AsyncIterator
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from backend.application.services._routes import HOT_ROUTES
from backend.application.services.flight_dates import is_canonical_depart_date
from backend.config import settings
from backend.data_sources.ctrip_source import CtripSource
from backend.infrastructure.db.alert_repo import list_active_alert_routes
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_demand_repo import (
    claim_due_demands,
    enqueue_demand,
)
from backend.infrastructure.db.flight_snapshot_repo import upsert_provider_flights
from backend.infrastructure.observability.provider_tracing import (
    trace_ctrip_demand,
    trace_ctrip_refresh,
)
from backend.utils.airport_codes import resolve_airport


CTRIP_WORKER_LEASE_KEY = 731_640_175
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CtripRefreshSummary:
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped_overlap: bool = False


@asynccontextmanager
async def try_ctrip_worker_lease() -> AsyncIterator[bool]:
    async with get_session() as session:
        acquired = bool(
            await session.scalar(
                select(func.pg_try_advisory_lock(CTRIP_WORKER_LEASE_KEY))
            )
        )
        try:
            yield acquired
        finally:
            if acquired:
                await session.execute(
                    select(func.pg_advisory_unlock(CTRIP_WORKER_LEASE_KEY))
                )


async def seed_ctrip_demands() -> None:
    for origin, destination, depart_date in await list_active_alert_routes():
        if not is_canonical_depart_date(depart_date):
            logger.warning(
                "ctrip_seed_alert_skipped origin=%s destination=%s "
                "depart_date=<invalid> reason=invalid_date",
                origin,
                destination,
            )
            continue
        origin_ref = resolve_airport(origin)
        destination_ref = resolve_airport(destination)
        if origin_ref is None or destination_ref is None:
            continue
        await _enqueue_seed_demand(
            origin_code=origin_ref.code,
            destination_code=destination_ref.code,
            depart_date=depart_date,
            priority=100,
            source="price_alert",
        )

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    for origin, destination in HOT_ROUTES:
        for offset in range(1, 4):
            await _enqueue_seed_demand(
                origin_code=origin,
                destination_code=destination,
                depart_date=(today + timedelta(days=offset)).isoformat(),
                priority=5,
                source="hot_route",
            )


async def _enqueue_seed_demand(
    *,
    origin_code: str,
    destination_code: str,
    depart_date: str,
    priority: int,
    source: str,
) -> None:
    try:
        await enqueue_demand(
            origin_code=origin_code,
            destination_code=destination_code,
            depart_date=depart_date,
            priority=priority,
            source=source,
        )
    except ValueError:
        safe_depart_date = (
            depart_date if is_canonical_depart_date(depart_date) else "<invalid>"
        )
        logger.warning(
            "ctrip_seed_demand_skipped origin=%s destination=%s "
            "depart_date=%s reason=rejected",
            origin_code,
            destination_code,
            safe_depart_date,
        )


async def refresh_ctrip_once() -> CtripRefreshSummary:
    return await trace_ctrip_refresh(_refresh_ctrip_once)


async def _refresh_ctrip_once() -> CtripRefreshSummary:
    async with try_ctrip_worker_lease() as acquired:
        if not acquired:
            summary = CtripRefreshSummary(skipped_overlap=True)
            _log_summary(summary)
            return summary

        await seed_ctrip_demands()
        demands = await claim_due_demands(settings.ctrip_refresh_batch_size)
        source = CtripSource(
            enable_mock_fallback=False,
            headless=True,
            collection_timeout_seconds=(
                settings.ctrip_collection_timeout_seconds
            ),
        )
        succeeded = 0
        failed = 0

        for demand in demands:
            valid_depart_date = is_canonical_depart_date(demand.depart_date)
            if valid_depart_date:
                operation = lambda: source.search_flights(
                    demand.origin_code,
                    demand.destination_code,
                    demand.depart_date,
                    demand.depart_date,
                )
            else:
                operation = _reject_invalid_depart_date
            try:
                rows = await trace_ctrip_demand(
                    origin_code=demand.origin_code,
                    destination_code=demand.destination_code,
                    depart_date=demand.depart_date,
                    operation=operation,
                )
                await upsert_provider_flights(
                    "ctrip_snapshot",
                    rows,
                    ttl_minutes=settings.ctrip_snapshot_ttl_minutes,
                    origin_code=demand.origin_code,
                    destination_code=demand.destination_code,
                    depart_date=demand.depart_date,
                )
                succeeded += 1
            except Exception:
                failed += 1
                logger.warning(
                    "ctrip_refresh_demand_failed origin=%s destination=%s "
                    "depart_date=%s",
                    demand.origin_code,
                    demand.destination_code,
                    demand.depart_date if valid_depart_date else "<invalid>",
                )
            await asyncio.sleep(
                random.uniform(
                    settings.ctrip_request_delay_min_seconds,
                    settings.ctrip_request_delay_max_seconds,
                )
            )

        summary = CtripRefreshSummary(
            processed=len(demands),
            succeeded=succeeded,
            failed=failed,
        )
        _log_summary(summary)
        return summary


async def _reject_invalid_depart_date():
    raise ValueError("demand depart_date is invalid")


def _log_summary(summary: CtripRefreshSummary) -> None:
    logger.info(
        "ctrip_refresh_complete processed=%d succeeded=%d failed=%d skipped=%d",
        summary.processed,
        summary.succeeded,
        summary.failed,
        int(summary.skipped_overlap),
    )
