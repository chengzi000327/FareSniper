from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.config import settings
from backend.infrastructure.db import flight_demand_repo
from backend.infrastructure.db.flight_demand_repo import (
    CollectorJobNotFoundError,
    LeaseOwnershipError,
)
from backend.infrastructure.observability.collector_tracing import (
    trace_collector_claim,
    trace_collector_ingest,
)
from backend.schemas.collector import (
    ClaimRequest,
    ClaimResponse,
    CollectorJobResponse,
    CompleteRequest,
    FailRequest,
    HeartbeatRequest,
)


class CollectorRoute(APIRoute):
    def get_route_handler(
        self,
    ) -> Callable[[Request], Awaitable[Response]]:
        original_handler = super().get_route_handler()

        async def safe_validation_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "invalid collector request"},
                )

        return safe_validation_handler


router = APIRouter(
    prefix="/internal/collector",
    tags=["collector"],
    route_class=CollectorRoute,
)


def require_collector_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.ctrip_collector_token
    scheme, separator, candidate = (authorization or "").partition(" ")
    supplied = candidate if separator and scheme == "Bearer" else ""
    matches = secrets.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    )
    if not expected.strip() or not matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/claim",
    response_model=ClaimResponse,
    dependencies=[Depends(require_collector_token)],
)
async def claim(request: ClaimRequest) -> ClaimResponse:
    job = await trace_collector_claim(
        lambda: flight_demand_repo.claim_next(
            request.node_id,
            lease_seconds=settings.ctrip_collector_lease_seconds,
        )
    )
    if job is None:
        return ClaimResponse(job=None)
    return ClaimResponse(
        job=CollectorJobResponse(
            job_id=job.job_id,
            origin_code=job.origin_code,
            destination_code=job.destination_code,
            depart_date=job.depart_date,
            source=job.source,
            priority=job.priority,
            attempts=job.attempts,
            lease_expires_at=job.lease_expires_at,
        )
    )


@router.post(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_collector_token)],
)
async def heartbeat(request: HeartbeatRequest) -> Response:
    await flight_demand_repo.record_heartbeat(
        request.node_id,
        request.version,
        request.status,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/jobs/{job_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_collector_token)],
)
async def complete(job_id: str, request: CompleteRequest) -> Response:
    offers = [offer.to_internal_offer() for offer in request.offers]
    try:
        await trace_collector_ingest(
            job_id,
            len(offers),
            lambda: flight_demand_repo.complete_job(
                job_id,
                request.node_id,
                offers,
            ),
        )
    except (CollectorJobNotFoundError, LeaseOwnershipError, ValueError):
        _raise_job_unavailable()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/jobs/{job_id}/fail",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_collector_token)],
)
async def fail(job_id: str, request: FailRequest) -> Response:
    try:
        await flight_demand_repo.fail_job(
            job_id,
            request.node_id,
            request.error_code.value,
            request.retry_at,
        )
    except (CollectorJobNotFoundError, LeaseOwnershipError, ValueError):
        _raise_job_unavailable()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _raise_job_unavailable() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="job unavailable",
    )
