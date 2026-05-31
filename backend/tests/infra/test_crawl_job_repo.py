from __future__ import annotations

import pytest

from backend.infrastructure.db.crawl_job_repo import (
    get_crawl_job,
    mark_crawl_job_failed,
    mark_crawl_job_success,
    start_crawl_job,
    update_platform_status,
)


@pytest.mark.asyncio
async def test_crawl_job_lifecycle(seeded_pg):
    job_id = await start_crawl_job(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )

    running = await get_crawl_job(job_id)
    assert running is not None
    assert running["route_key"] == "BJS-SHA-2026-05-08"
    assert running["status"] == "running"
    assert running["started_at"] is not None

    await update_platform_status(job_id, {"ctrip": {"status": "ok", "rows": 1}})
    await mark_crawl_job_success(job_id, {"ctrip": {"status": "ok", "rows": 1}})

    done = await get_crawl_job(job_id)
    assert done is not None
    assert done["status"] == "success"
    assert done["platform_status"]["ctrip"]["rows"] == 1
    assert done["finished_at"] is not None


@pytest.mark.asyncio
async def test_mark_crawl_job_failed_records_error(seeded_pg):
    job_id = await start_crawl_job(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )

    await mark_crawl_job_failed(
        job_id,
        error_message="boom",
        platform_status={"ctrip": {"status": "failed"}},
    )

    row = await get_crawl_job(job_id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error_message"] == "boom"
    assert row["platform_status"]["ctrip"]["status"] == "failed"
    assert row["finished_at"] is not None
