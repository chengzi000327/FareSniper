from __future__ import annotations

import pytest

from backend.infrastructure.db.crawl_job_repo import (
    get_crawl_job,
    start_crawl_job as real_start_crawl_job,
)
from backend.infrastructure.db.flight_snapshot_repo import read_deals
from backend.infrastructure.scrapers.multi_platform import (
    crawl_route,
    scrape_all_routes,
    scrape_route_all_platforms,
)


@pytest.mark.asyncio
async def test_scrape_route_aggregates_5_platforms(stub_playwright):
    deals = await scrape_route_all_platforms(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )
    platforms = {d["platform"] for d in deals}
    assert platforms == {"ctrip", "qunar", "tongcheng", "fliggy", "umetrip"}
    assert all(d.get("source") == "fake" for d in deals)


@pytest.mark.asyncio
async def test_scrape_all_routes_skips_fake_source(seeded_pg, stub_playwright):
    """Placeholder deals (source='fake') must not be written to snapshot tables."""
    await scrape_all_routes()
    deals = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2026-05-08"
    )
    assert deals == []


@pytest.mark.asyncio
async def test_scrape_all_routes_writes_real_source(seeded_pg, monkeypatch):
    """Real deals (source='scrape') must be written to snapshot tables."""
    real_deals = [
        {
            "flight_number": "MU5137",
            "price": 480,
            "platform": "ctrip",
            "airline": "东方航空",
            "dep_city": "北京",
            "arr_city": "上海",
            "dep_time": "08:30",
            "arr_time": "11:00",
            "duration": "2h30m",
            "transfer_count": 0,
            "date": "2026-05-08",
            "source": "scrape",
        }
    ]

    async def fake_route(*, origin, destination, depart_date):
        if (origin, destination, depart_date) == ("BJS", "SHA", "2026-05-08"):
            return real_deals
        return []

    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.scrape_route_all_platforms",
        fake_route,
    )
    await scrape_all_routes()
    deals = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2026-05-08"
    )
    assert deals and deals[0]["flight_no"] == "MU5137"


@pytest.mark.asyncio
async def test_crawl_route_persists_valid_rows_and_skips_fake(seeded_pg, monkeypatch):
    rows = [
        {
            "flight_number": "MU5137",
            "price": 480,
            "platform": "ctrip",
            "airline": "东方航空",
            "dep_city": "北京",
            "arr_city": "上海",
            "dep_time": "08:30",
            "arr_time": "11:00",
            "duration": "2h30m",
            "transfer_count": 0,
            "date": "2026-05-08",
            "source": "scrape",
        },
        {
            "flight_number": "FAKE1",
            "price": 1,
            "platform": "qunar",
            "dep_city": "北京",
            "arr_city": "上海",
            "dep_time": "09:30",
            "date": "2026-05-08",
            "source": "fake",
        },
    ]

    async def fake_route(*, origin, destination, depart_date):
        return rows

    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.scrape_route_all_platforms",
        fake_route,
    )

    job_id = await crawl_route(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )

    deals = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2026-05-08"
    )
    assert [d["flight_no"] for d in deals] == ["MU5137"]

    job = await get_crawl_job(job_id)
    assert job is not None
    assert job["status"] == "success"
    assert job["platform_status"]["ctrip"]["persisted_rows"] == 1
    assert job["platform_status"]["qunar"]["skipped_fake_rows"] == 1


@pytest.mark.asyncio
async def test_crawl_route_marks_job_failed_on_exception(seeded_pg, monkeypatch):
    job_ids: list[str] = []

    async def tracking_start_crawl_job(*, origin, destination, depart_date):
        job_id = await real_start_crawl_job(
            origin=origin, destination=destination, depart_date=depart_date
        )
        job_ids.append(job_id)
        return job_id

    async def broken_route(*, origin, destination, depart_date):
        raise RuntimeError("scraper down")

    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.start_crawl_job",
        tracking_start_crawl_job,
    )
    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.scrape_route_all_platforms",
        broken_route,
    )

    with pytest.raises(RuntimeError, match="scraper down"):
        await crawl_route(origin="BJS", destination="SHA", depart_date="2026-05-08")

    job = await get_crawl_job(job_ids[0])
    assert job is not None
    assert job["status"] == "failed"
    assert job["error_message"] == "scraper down"
