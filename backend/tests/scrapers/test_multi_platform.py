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
async def test_scrape_all_routes_skips_fake_source(seeded_pg, monkeypatch):
    """Placeholder deals (source='fake') must not be written to snapshot tables.

    variflight_search is stubbed to return empty → nothing written to DB.
    """
    import backend.infrastructure.scrapers.multi_platform as mp
    from backend.infrastructure.flight_data.variflight_client import VariflightResult

    async def _empty(origin, destination, depart_date):
        return VariflightResult(rows=[])

    monkeypatch.setattr(mp, "variflight_search_with_status", _empty)
    await scrape_all_routes()
    # Dynamic routes cover next-3-days BJS hot routes, none with this old date
    deals = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2026-05-08"
    )
    assert deals == []


@pytest.mark.asyncio
async def test_scrape_all_routes_writes_real_source(seeded_pg, monkeypatch):
    """Real variflight deals must be written to snapshot tables."""
    from datetime import date, timedelta

    import backend.infrastructure.scrapers.multi_platform as mp

    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    real_deals = [
        {
            "flight_no": "MU5137",
            "price": 480,
            "platform": "variflight",
            "airline": "东方航空",
            "dep_city": "北京",
            "arr_city": "上海",
            "date": tomorrow,
            "dep_time": "08:30",
            "arr_time": "11:00",
            "duration": "2h30m",
            "transfer_count": 0,
        }
    ]

    from backend.infrastructure.flight_data.variflight_client import VariflightResult

    async def _stub_variflight(origin, destination, depart_date):
        if origin == "BJS" and destination == "SHA":
            return VariflightResult(rows=real_deals)
        return VariflightResult(rows=[])

    monkeypatch.setattr(mp, "variflight_search_with_status", _stub_variflight)
    await scrape_all_routes()
    deals = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date=tomorrow
    )
    assert deals and deals[0]["flight_no"] == "MU5137"


@pytest.mark.asyncio
async def test_crawl_route_persists_valid_rows_and_skips_fake(seeded_pg, monkeypatch):
    """variflight rows get written; job status = success."""
    import backend.infrastructure.scrapers.multi_platform as mp

    variflight_rows = [
        {
            "flight_no": "MU5137",
            "price": 480,
            "platform": "variflight",
            "airline": "东方航空",
            "dep_city": "北京",
            "arr_city": "上海",
            "date": "2026-05-08",
            "dep_time": "08:30",
            "arr_time": "11:00",
            "duration": "2h30m",
            "transfer_count": 0,
        }
    ]

    from backend.infrastructure.flight_data.variflight_client import VariflightResult

    async def _stub(origin, destination, depart_date):
        return VariflightResult(rows=variflight_rows)

    monkeypatch.setattr(mp, "variflight_search_with_status", _stub)

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


@pytest.mark.asyncio
async def test_crawl_route_marks_job_failed_on_exception(seeded_pg, monkeypatch):
    import backend.infrastructure.scrapers.multi_platform as mp

    job_ids: list[str] = []

    async def tracking_start_crawl_job(*, origin, destination, depart_date):
        job_id = await real_start_crawl_job(
            origin=origin, destination=destination, depart_date=depart_date
        )
        job_ids.append(job_id)
        return job_id

    async def broken_variflight(origin, destination, depart_date):
        raise RuntimeError("scraper down")

    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.start_crawl_job",
        tracking_start_crawl_job,
    )
    monkeypatch.setattr(mp, "variflight_search_with_status", broken_variflight)

    with pytest.raises(RuntimeError, match="scraper down"):
        await crawl_route(origin="BJS", destination="SHA", depart_date="2026-05-08")

    job = await get_crawl_job(job_ids[0])
    assert job is not None
    assert job["status"] == "failed"
    assert job["error_message"] == "scraper down"


@pytest.mark.asyncio
async def test_crawl_route_marks_failed_on_datasource_error_zero_rows(
    seeded_pg, monkeypatch
):
    """数据源报错(API/网络/限流)且落库 0 行 → job 标记 failed,而非 success。"""
    import backend.infrastructure.scrapers.multi_platform as mp
    from backend.infrastructure.flight_data.variflight_client import VariflightResult

    async def _errored(origin, destination, depart_date):
        # rows 为空但 error 非 None：代表「数据源报错」,非「正常无航班」。
        return VariflightResult(rows=[], error="http_429")

    monkeypatch.setattr(mp, "variflight_search_with_status", _errored)

    job_id = await crawl_route(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )

    job = await get_crawl_job(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert "http_429" in (job["error_message"] or "")
    # platform_status 应记录飞常准的失败原因。
    vf = job["platform_status"].get("variflight")
    assert vf is not None
    assert vf["status"] == "error"
    assert vf["error"] == "http_429"


@pytest.mark.asyncio
async def test_crawl_route_marks_success_on_empty_no_error(seeded_pg, monkeypatch):
    """正常无航班(empty,error 为 None)→ job 仍标记 success。"""
    import backend.infrastructure.scrapers.multi_platform as mp
    from backend.infrastructure.flight_data.variflight_client import VariflightResult

    async def _empty(origin, destination, depart_date):
        return VariflightResult(rows=[], error=None)

    monkeypatch.setattr(mp, "variflight_search_with_status", _empty)

    job_id = await crawl_route(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )

    job = await get_crawl_job(job_id)
    assert job is not None
    assert job["status"] == "success"
