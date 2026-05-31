from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB

from backend.infrastructure.db.base import Base, get_session


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = {"extend_existing": True}

    job_id = Column(String, primary_key=True)
    route_key = Column(String, nullable=False)
    origin_code = Column(String, nullable=False)
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    platform_status = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


def _route_key(origin: str, destination: str, depart_date: str) -> str:
    return f"{origin}-{destination}-{depart_date}"


def _to_dict(job: CrawlJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "route_key": job.route_key,
        "origin_code": job.origin_code,
        "destination_code": job.destination_code,
        "depart_date": job.depart_date,
        "status": job.status,
        "platform_status": job.platform_status or {},
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_message": job.error_message,
    }


async def start_crawl_job(
    *, origin: str, destination: str, depart_date: str
) -> str:
    now = datetime.now(timezone.utc)
    job = CrawlJob(
        job_id=uuid4().hex,
        route_key=_route_key(origin, destination, depart_date),
        origin_code=origin,
        destination_code=destination,
        depart_date=depart_date,
        status="running",
        platform_status={},
        started_at=now,
    )
    async with get_session() as s:
        s.add(job)
        await s.commit()
    return job.job_id


async def update_platform_status(
    job_id: str, platform_status: dict[str, Any]
) -> None:
    async with get_session() as s:
        job = await s.get(CrawlJob, job_id)
        if job is None:
            return
        job.platform_status = platform_status
        await s.commit()


async def mark_crawl_job_success(
    job_id: str, platform_status: dict[str, Any] | None = None
) -> None:
    async with get_session() as s:
        job = await s.get(CrawlJob, job_id)
        if job is None:
            return
        job.status = "success"
        if platform_status is not None:
            job.platform_status = platform_status
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = None
        await s.commit()


async def mark_crawl_job_failed(
    job_id: str,
    *,
    error_message: str,
    platform_status: dict[str, Any] | None = None,
) -> None:
    async with get_session() as s:
        job = await s.get(CrawlJob, job_id)
        if job is None:
            return
        job.status = "failed"
        if platform_status is not None:
            job.platform_status = platform_status
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error_message
        await s.commit()


async def get_crawl_job(job_id: str) -> dict[str, Any] | None:
    async with get_session() as s:
        job = (
            await s.execute(select(CrawlJob).where(CrawlJob.job_id == job_id))
        ).scalar_one_or_none()
        return _to_dict(job) if job is not None else None
