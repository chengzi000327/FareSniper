from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import AsyncIterator
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from backend.application.services.airport_catalog import AirportCatalog
from backend.application.services._routes import HOT_ROUTES
from backend.application.services.flight_dates import is_canonical_depart_date
from backend.infrastructure.db.alert_repo import list_active_alert_routes
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_demand_repo import enqueue_demand
from backend.infrastructure.observability.provider_tracing import (
    trace_ctrip_refresh,
)
from backend.utils.airport_codes import resolve_airport


CTRIP_WORKER_LEASE_KEY = 731_640_175
logger = logging.getLogger(__name__)
_AIRPORT_CATALOG = AirportCatalog.load_default()


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


async def seed_ctrip_demands() -> int:
    seeded = 0
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    for origin, destination, depart_date in await list_active_alert_routes():
        if not is_canonical_depart_date(depart_date):
            logger.warning(
                "ctrip_seed_alert_skipped origin=%s destination=%s "
                "depart_date=<invalid> reason=invalid_date",
                origin,
                destination,
            )
            continue
        if date.fromisoformat(depart_date) <= today:
            logger.warning(
                "ctrip_seed_alert_skipped origin=%s destination=%s "
                "depart_date=%s reason=non_future",
                origin,
                destination,
                depart_date,
            )
            continue
        origin_code = _ctrip_code(origin)
        destination_code = _ctrip_code(destination)
        if origin_code is None or destination_code is None:
            continue
        seeded += await _enqueue_seed_demand(
            origin_code=origin_code,
            destination_code=destination_code,
            depart_date=depart_date,
            priority=100,
            source="price_alert",
        )

    for origin, destination in HOT_ROUTES:
        origin_code = _ctrip_code(origin)
        destination_code = _ctrip_code(destination)
        if origin_code is None or destination_code is None:
            continue
        for offset in range(1, 4):
            seeded += await _enqueue_seed_demand(
                origin_code=origin_code,
                destination_code=destination_code,
                depart_date=(today + timedelta(days=offset)).isoformat(),
                priority=5,
                source="hot_route",
            )
    return seeded


def _ctrip_code(value: str) -> str | None:
    location = _AIRPORT_CATALOG.resolve_location(value)
    if location is not None:
        return location.provider_code("ctrip")
    ref = resolve_airport(value)
    return ref.code if ref is not None else None


async def _enqueue_seed_demand(
    *,
    origin_code: str,
    destination_code: str,
    depart_date: str,
    priority: int,
    source: str,
) -> bool:
    try:
        await enqueue_demand(
            origin_code=origin_code,
            destination_code=destination_code,
            depart_date=depart_date,
            priority=priority,
            source=source,
            reactivate_completed=False,
        )
        return True
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
        return False


async def refresh_ctrip_once() -> CtripRefreshSummary:
    return await trace_ctrip_refresh(_refresh_ctrip_once)


async def _refresh_ctrip_once() -> CtripRefreshSummary:
    async with try_ctrip_worker_lease() as acquired:
        if not acquired:
            summary = CtripRefreshSummary(skipped_overlap=True)
            _log_summary(summary)
            return summary

        seeded = await seed_ctrip_demands()
        summary = CtripRefreshSummary(
            processed=seeded,
            succeeded=seeded,
        )
        _log_summary(summary)
        return summary

def _log_summary(summary: CtripRefreshSummary) -> None:
    logger.info(
        "ctrip_refresh_complete processed=%d succeeded=%d failed=%d skipped=%d",
        summary.processed,
        summary.succeeded,
        summary.failed,
        int(summary.skipped_overlap),
    )
