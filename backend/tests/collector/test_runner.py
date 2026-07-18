from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.collector.browser import CaptureResult
from backend.collector.runner import CollectorRunner


@pytest.fixture
def job():
    return SimpleNamespace(
        job_id="job-1",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-08",
    )


@pytest.fixture
def ctrip_payload():
    path = (
        Path(__file__).parents[1]
        / "fixtures/providers/ctrip_batch_search.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    flight = payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight.update(
        {
            "departureCityCode": "BJS",
            "arrivalCityCode": "SHA",
            "departureDateTime": "2099-08-08 08:00:00",
            "arrivalDateTime": "2099-08-08 10:20:00",
        }
    )
    return payload


class FakeApi:
    def __init__(self, job):
        self.job = job
        self.calls: list[tuple] = []
        self.complete_calls: list[tuple] = []
        self.fail_calls: list[tuple] = []

    async def heartbeat(self, status):
        self.calls.append(("heartbeat", status))

    async def claim(self):
        self.calls.append(("claim",))
        claimed, self.job = self.job, None
        return claimed

    async def complete(self, job_id, offers):
        self.calls.append(("complete", job_id))
        self.complete_calls.append((job_id, offers))

    async def fail(self, job_id, error_code, retry_at):
        self.calls.append(("fail", job_id, error_code))
        self.fail_calls.append((job_id, error_code, retry_at))


class FakeBrowser:
    def __init__(self, result):
        self.result = result
        self.active = 0
        self.max_active = 0

    async def capture(self, _job):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return self.result
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_run_once_heartbeats_and_claims_exactly_one_job():
    api = FakeApi(job=None)
    runner = CollectorRunner(api, FakeBrowser(CaptureResult()))

    result = await runner.run_once()

    assert result.status == "idle"
    assert api.calls == [("heartbeat", "idle"), ("claim",)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_code",
    [
        CollectorErrorCode.login_required,
        CollectorErrorCode.captcha_required,
        CollectorErrorCode.timeout,
    ],
)
async def test_runner_fails_explicit_browser_status_once(job, error_code):
    api = FakeApi(job)
    browser = FakeBrowser(CaptureResult(error_code=error_code))
    runner = CollectorRunner(
        api,
        browser,
        now=lambda: datetime(2099, 8, 1, tzinfo=timezone.utc),
    )

    result = await runner.run_once()

    assert result.status == error_code.value
    assert len(api.fail_calls) == 1
    assert api.fail_calls[0][1] is error_code
    assert api.complete_calls == []


@pytest.mark.asyncio
async def test_runner_completes_with_normalized_real_offers(
    job, ctrip_payload
):
    api = FakeApi(job)
    runner = CollectorRunner(
        api,
        FakeBrowser(CaptureResult(payloads=[ctrip_payload])),
    )

    result = await runner.run_once()

    assert result.status == "success"
    assert len(api.complete_calls) == 1
    offers = api.complete_calls[0][1]
    assert offers[0].seller_name == "携程"
    assert offers[0].total_price > 0
    assert offers[0].booking_url == (
        "https://flights.ctrip.com/online/list/oneway-bjs-sha"
        "?depdate=2099-08-08"
    )
    assert api.fail_calls == []


@pytest.mark.asyncio
async def test_empty_inventory_fails_without_overwriting_snapshot(
    job, ctrip_payload
):
    ctrip_payload["data"]["flightItineraryList"] = []
    api = FakeApi(job)
    runner = CollectorRunner(
        api,
        FakeBrowser(CaptureResult(payloads=[ctrip_payload])),
    )

    result = await runner.run_once()

    assert result.status == "empty"
    assert api.complete_calls == []
    assert api.fail_calls[0][1] is CollectorErrorCode.empty


@pytest.mark.asyncio
async def test_parser_error_fails_once(job):
    api = FakeApi(job)
    runner = CollectorRunner(
        api,
        FakeBrowser(CaptureResult(payloads=[{"data": {}}])),
    )

    result = await runner.run_once()

    assert result.status == "parse_error"
    assert len(api.fail_calls) == 1
    assert api.complete_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("departureCityCode", "CAN"),
        ("arrivalCityCode", "CAN"),
        ("departureDateTime", "2099-08-07 08:00:00"),
    ],
)
async def test_mismatched_payload_scope_fails_without_upload(
    job,
    ctrip_payload,
    field,
    value,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight[field] = value
    api = FakeApi(job)
    runner = CollectorRunner(
        api,
        FakeBrowser(CaptureResult(payloads=[ctrip_payload])),
    )

    result = await runner.run_once()

    assert result.status == "parse_error"
    assert api.complete_calls == []
    assert len(api.fail_calls) == 1
    assert api.fail_calls[0][1] is CollectorErrorCode.parse_error


@pytest.mark.asyncio
async def test_daemon_runs_one_task_at_a_time_and_stops(job, ctrip_payload):
    api = FakeApi(job)
    browser = FakeBrowser(CaptureResult(payloads=[ctrip_payload]))
    runner = CollectorRunner(api, browser)
    stop = SimpleNamespace(is_set=lambda: len(api.calls) >= 3)

    async def wait_for_stop(_seconds):
        return stop.is_set()

    await runner.run_daemon(
        stop_requested=stop.is_set,
        interval_seconds=60,
        wait_for_stop=wait_for_stop,
    )

    assert browser.max_active == 1
    assert len(api.complete_calls) == 1
