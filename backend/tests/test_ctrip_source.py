"""
Step 7 CtripSource 测试
不启动真实浏览器，只测试 normalize() 逻辑和 import 失败降级。
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import signal
import sys
from types import SimpleNamespace

import pytest

from backend.data_sources.ctrip_source import CtripCollectionError, CtripSource


SENSITIVE_SENTINEL = "SENSITIVE_SENTINEL_DO_NOT_LOG"


def test_ctrip_source_defaults_to_no_mock_fallback():
    assert CtripSource().enable_mock_fallback is False


# ── raw flight dict（模拟 CtripFlightClient.search_oneway 返回的一条记录）──

def _raw_flight(**overrides) -> dict:
    base = {
        "flight_number": "CA901",
        "airline": "中国国航",
        "dep_city": "北京",
        "arr_city": "东京",
        "dep_airport": "首都国际机场",
        "arr_airport": "成田国际机场",
        "dep_time": "2026-05-01 08:00:00",
        "arr_time": "2026-05-01 13:30:00",
        "duration": 210,
        "transfer_time": 0,
        "transfer_count": 0,
        "transfer_cities": [],
        "price": 2580,
        "discount_rate": 0.75,
        "discount_display": "7.5折",
        "date": "2026-05-01",
    }
    return {**base, **overrides}


def test_normalize_basic_fields():
    """normalize 把 raw dict 转换为含 DealCardDto 必需字段的 dict。"""
    source = CtripSource(enable_mock_fallback=False)
    result = source._normalize(_raw_flight(), origin="PEK", destination="NRT")

    assert result["platform"] == "携程"
    assert result["origin_code"] == "PEK"
    assert result["destination_code"] == "NRT"
    assert result["price"] == 2580
    assert result["airline"] == "中国国航"


def test_normalize_real_result_has_only_ctrip_seller_and_unknown_fees():
    source = CtripSource(enable_mock_fallback=False)
    result = source._normalize(
        _raw_flight(url="https://flights.ctrip.com/booking/CA901"),
        origin="PEK",
        destination="NRT",
    )

    assert result["tax"] is None
    assert result["baggage_fee"] is None
    assert result["has_baggage"] is None
    assert result["currency"] == "CNY"
    assert result["recommend_score"] is None
    assert result["flight_no"] == "CA901"
    assert result["dep_time"] == "08:00"
    assert result["arr_time"] == "13:30"
    assert result["duration"] == "210"
    assert result["stops"] == 0
    assert result["prices"] == [
        {
            "platform": "携程",
            "price": 2580,
            "currency": "CNY",
            "url": "https://flights.ctrip.com/booking/CA901",
        }
    ]
    assert result["booking_url"] == "https://flights.ctrip.com/booking/CA901"


def test_normalize_system_id():
    """normalize 生成非空的 system_id（格式 SYS.XXX）。"""
    source = CtripSource()
    result = source._normalize(_raw_flight(), origin="PEK", destination="NRT")

    assert "system_id" in result
    assert result["system_id"].startswith("SYS.")


def test_normalize_city_names():
    """normalize 从 raw dict 提取 origin_city / destination_city。"""
    source = CtripSource()
    result = source._normalize(_raw_flight(), origin="PEK", destination="NRT")

    assert result["origin_city"] == "北京"
    assert result["destination_city"] == "东京"


def test_normalize_confidence():
    """discount_rate >= 0.7 时 confidence 为 high，否则 medium。"""
    source = CtripSource()

    high = source._normalize(_raw_flight(discount_rate=0.65), origin="PEK", destination="NRT")
    medium = source._normalize(_raw_flight(discount_rate=0.85), origin="PEK", destination="NRT")

    assert high["confidence"] == "high"
    assert medium["confidence"] == "medium"


def test_normalize_verdict():
    """normalize 生成非空的 verdict 字符串。"""
    source = CtripSource()
    result = source._normalize(_raw_flight(), origin="PEK", destination="NRT")

    assert isinstance(result["verdict"], str)
    assert len(result["verdict"]) > 0


def test_normalize_depart_time_format():
    """depart_time / arrive_time 格式化为 HH:mm。"""
    source = CtripSource()
    result = source._normalize(
        _raw_flight(dep_time="2026-05-01 08:05:00", arr_time="2026-05-01 13:35:00"),
        origin="PEK", destination="NRT",
    )

    assert result["depart_time"] == "08:05"
    assert result["arrive_time"] == "13:35"


def test_normalize_discount_rate():
    """discount_rate 和 original_price 正确写入。"""
    source = CtripSource()
    result = source._normalize(_raw_flight(price=2580, discount_rate=0.75), origin="PEK", destination="NRT")

    assert result["discount_rate"] == 0.75
    assert result["original_price"] is not None
    assert result["original_price"] > result["price"]


@pytest.mark.asyncio
async def test_production_import_failure_raises_typed_sanitized_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctrip_api", None)
    monkeypatch.setitem(sys.modules, "shared", None)
    _install_fake_client(monkeypatch, flights=[], got_response=False)
    source = CtripSource(enable_mock_fallback=False)

    with pytest.raises(CtripCollectionError) as exc_info:
        await source.search_flights("PEK", "NRT", "2099-08-01", "2099-08-01")

    assert str(exc_info.value) == "Ctrip browser collection failed"


@pytest.mark.asyncio
async def test_import_failure_uses_mock_fallback_when_enabled(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctrip_api", None)
    monkeypatch.setitem(sys.modules, "shared", None)
    _install_fake_client(monkeypatch, flights=[], got_response=False)
    source = CtripSource(enable_mock_fallback=True)

    results = await source.search_flights(
        "PEK", "NRT", "2099-08-01", "2099-08-01"
    )

    assert len(results) > 0


@pytest.mark.asyncio
async def test_no_response_raises_typed_sanitized_error(monkeypatch):
    _install_fake_client(monkeypatch, flights=[], got_response=False)
    source = CtripSource(enable_mock_fallback=False, headless=True)

    with pytest.raises(CtripCollectionError) as exc_info:
        await source.search_flights("PEK", "NRT", "2099-08-01", "2099-08-01")

    assert str(exc_info.value) == "Ctrip browser collection failed"


@pytest.mark.asyncio
async def test_valid_empty_response_is_success(monkeypatch):
    _install_fake_client(monkeypatch, flights=[], got_response=True)
    source = CtripSource(enable_mock_fallback=True, headless=True)

    results = await source.search_flights(
        "PEK", "NRT", "2099-08-01", "2099-08-01"
    )

    assert results == []


@pytest.mark.asyncio
async def test_browser_failure_is_sanitized_and_propagated(monkeypatch):
    async def fail_worker(self, *args):
        raise RuntimeError(SENSITIVE_SENTINEL)

    async def no_retry_delay(fn, *args, **kwargs):
        return await fn(*args)

    monkeypatch.setattr(CtripSource, "_run_worker_once", fail_worker)
    monkeypatch.setattr(
        "backend.data_sources.ctrip_source.retry_with_backoff", no_retry_delay
    )

    source = CtripSource(enable_mock_fallback=False, headless=True)
    with pytest.raises(CtripCollectionError) as exc_info:
        await source.search_flights(
            "PEK", "NRT", "2099-08-01", "2099-08-01"
        )

    assert str(exc_info.value) == "Ctrip browser collection failed"
    assert SENSITIVE_SENTINEL not in str(exc_info.value)


@pytest.mark.asyncio
async def test_hanging_navigation_kills_browser_process_group_without_live_browser(
    monkeypatch,
):
    communicate_started = asyncio.Event()
    waited = asyncio.Event()
    launches = []
    killed: list[tuple[int, signal.Signals]] = []

    class HangingProcess:
        pid = 42001
        returncode = None

        async def communicate(self):
            communicate_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def wait(self):
            self.returncode = -signal.SIGKILL
            waited.set()
            return self.returncode

    async def fake_create(*args, **kwargs):
        launches.append((args, kwargs))
        return HangingProcess()

    async def no_retry(fn, *args, **kwargs):
        return await fn(*args)

    def fake_killpg(process_group: int, sig: signal.Signals) -> None:
        killed.append((process_group, sig))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", fake_killpg)
    monkeypatch.setattr(
        "backend.data_sources.ctrip_source.retry_with_backoff", no_retry
    )
    source = CtripSource(
        enable_mock_fallback=False,
        headless=True,
        collection_timeout_seconds=0.001,
    )

    with pytest.raises(CtripCollectionError):
        await source.search_flights("BJS", "SHA", "2099-08-01", "2099-08-01")

    assert communicate_started.is_set()
    assert launches[0][1]["start_new_session"] is True
    assert killed == [(42001, signal.SIGKILL)]
    assert waited.is_set()


@pytest.mark.asyncio
async def test_malformed_worker_payload_kills_process_group_and_awaits_cleanup(
    monkeypatch,
):
    waited = asyncio.Event()
    killed: list[tuple[int, signal.Signals]] = []

    class MalformedProcess:
        pid = 42002
        returncode = 0

        async def communicate(self):
            return b'{"ok":false}', b""

        async def wait(self):
            waited.set()
            return self.returncode

    async def fake_create(*args, **kwargs):
        return MalformedProcess()

    def fake_killpg(process_group: int, sig: signal.Signals) -> None:
        killed.append((process_group, sig))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", fake_killpg)

    with pytest.raises(CtripCollectionError):
        await CtripSource(enable_mock_fallback=False)._run_worker_once(
            "BJS", "SHA", "2099-08-01", "2099-08-01"
        )

    assert killed == [(42002, signal.SIGKILL)]
    assert waited.is_set()


@pytest.mark.asyncio
async def test_successful_worker_payload_kills_process_group_and_awaits_cleanup(
    monkeypatch,
):
    waited = asyncio.Event()
    killed: list[tuple[int, signal.Signals]] = []

    class SuccessfulProcess:
        pid = 42003
        returncode = 0

        async def communicate(self):
            return b'{"ok":true,"flights":[]}', b""

        async def wait(self):
            waited.set()
            return self.returncode

    async def fake_create(*args, **kwargs):
        return SuccessfulProcess()

    def fake_killpg(process_group: int, sig: signal.Signals) -> None:
        killed.append((process_group, sig))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", fake_killpg)

    flights = await CtripSource(enable_mock_fallback=False)._run_worker_once(
        "BJS", "SHA", "2099-08-01", "2099-08-01"
    )

    assert flights == []
    assert killed == [(42003, signal.SIGKILL)]
    assert waited.is_set()


def test_ctrip_client_sets_a_page_load_timeout(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    driver = _FakeDriver("[]")
    monkeypatch.setattr(
        ctrip_api, "init_browser", lambda **kwargs: (driver, None)
    )
    client = ctrip_api.CtripFlightClient(headless=True)

    client.init_session()

    assert driver.page_load_timeout == client.PAGE_LOAD_TIMEOUT


def test_client_error_response_payload_is_not_logged_or_written(
    monkeypatch, tmp_path, caplog
):
    ctrip_api = _load_ctrip_api(monkeypatch)
    payload = json.dumps(
        {
            "code": SENSITIVE_SENTINEL,
            "msg": SENSITIVE_SENTINEL,
            "data": {"flightItineraryList": []},
        }
    )
    driver = _FakeDriver(json.dumps([payload]))
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = driver
    monkeypatch.setattr(ctrip_api, "WebDriverWait", _ImmediateWait)
    monkeypatch.setattr(ctrip_api.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ctrip_api.random, "uniform", lambda low, high: 0)
    monkeypatch.setattr(ctrip_api, "__file__", str(tmp_path / "ctrip_api.py"))
    caplog.set_level("DEBUG", logger=ctrip_api.__name__)

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is False
    assert SENSITIVE_SENTINEL not in caplog.text
    assert not (tmp_path / ".debug_response.json").exists()


def test_client_all_malformed_responses_are_not_valid(monkeypatch, caplog):
    ctrip_api, client = _real_client_with_responses(
        monkeypatch,
        [f"{{{SENSITIVE_SENTINEL}"],
    )
    caplog.set_level("DEBUG", logger=ctrip_api.__name__)

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is False
    assert SENSITIVE_SENTINEL not in caplog.text


@pytest.mark.asyncio
async def test_client_accepts_code_zero_empty_inventory_through_source(
    monkeypatch
):
    ctrip_api = _load_ctrip_api(monkeypatch)
    payload = json.dumps(
        {"code": 0, "data": {"flightItineraryList": []}}
    )
    driver = _FakeDriver(json.dumps([payload]))
    monkeypatch.setattr(
        ctrip_api, "init_browser", lambda **kwargs: (driver, None)
    )
    monkeypatch.setattr(ctrip_api.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ctrip_api.random, "uniform", lambda low, high: 0)

    with ctrip_api.CtripFlightClient(headless=True) as client:
        flights, got_response = client.search_oneway(
            "PEK", "NRT", "北京", "东京", "2099-08-01"
        )
    _install_fake_client(
        monkeypatch, flights=flights, got_response=got_response
    )

    source = CtripSource(enable_mock_fallback=False, headless=True)
    results = await source.search_flights(
        "PEK", "NRT", "2099-08-01", "2099-08-01"
    )

    assert results == []


def test_client_late_parse_exception_invalidates_response(monkeypatch, caplog):
    payload = json.dumps(
        {"code": 0, "data": {"flightItineraryList": []}}
    )
    ctrip_api, client = _real_client_with_responses(monkeypatch, [payload])

    def fail_after_recognition(*args, **kwargs):
        raise RuntimeError(SENSITIVE_SENTINEL)

    monkeypatch.setattr(client, "_parse_response", fail_after_recognition)
    caplog.set_level("DEBUG", logger=ctrip_api.__name__)

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is False
    assert SENSITIVE_SENTINEL not in caplog.text


@pytest.mark.parametrize(
    "inventory",
    [
        [{}],
        [{"flightSegments": [{}]}],
    ],
)
def test_client_rejects_inventory_when_every_item_is_structurally_invalid(
    monkeypatch, inventory
):
    payload = json.dumps(
        {"code": 0, "data": {"flightItineraryList": inventory}}
    )
    _, client = _real_client_with_responses(monkeypatch, [payload])

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is False


@pytest.mark.asyncio
async def test_structurally_invalid_inventory_raises_through_source(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    payload = json.dumps(
        {"code": 0, "data": {"flightItineraryList": [{}]}}
    )
    driver = _FakeDriver(json.dumps([payload]))

    monkeypatch.setattr(
        ctrip_api, "init_browser", lambda **kwargs: (driver, None)
    )
    monkeypatch.setattr(ctrip_api.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ctrip_api.random, "uniform", lambda low, high: 0)
    with ctrip_api.CtripFlightClient(headless=True) as client:
        flights, got_response = client.search_oneway(
            "PEK", "NRT", "北京", "东京", "2099-08-01"
        )
    _install_fake_client(
        monkeypatch, flights=flights, got_response=got_response
    )

    source = CtripSource(enable_mock_fallback=False, headless=True)
    with pytest.raises(CtripCollectionError):
        await source.search_flights(
            "PEK", "NRT", "2099-08-01", "2099-08-01"
        )


@pytest.mark.parametrize(
    "price_list",
    [
        [],
        [{"cabin": "C", "adultPrice": 800}],
    ],
)
def test_client_accepts_structurally_valid_inventory_filtered_without_fares(
    monkeypatch, price_list
):
    item = {
        "flightSegments": [
            {
                "flightList": [
                    {
                        "flightNo": "CA901",
                        "marketAirlineName": "Airline",
                        "departureDateTime": "2099-08-01 08:00:00",
                        "arrivalDateTime": "2099-08-01 10:00:00",
                        "duration": 120,
                    }
                ]
            }
        ],
        "priceList": price_list,
    }
    payload = json.dumps(
        {"code": 0, "data": {"flightItineraryList": [item]}}
    )
    _, client = _real_client_with_responses(monkeypatch, [payload])

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is True


def test_client_exception_text_is_not_logged(monkeypatch, caplog):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _FailingDriver()
    monkeypatch.setattr(ctrip_api.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ctrip_api.random, "uniform", lambda low, high: 0)
    caplog.set_level("DEBUG", logger=ctrip_api.__name__)

    flights, got_response = client.search_oneway(
        "PEK", "NRT", "北京", "东京", "2099-08-01"
    )

    assert flights == []
    assert got_response is False
    assert SENSITIVE_SENTINEL not in caplog.text


def test_mock_fallback_returns_deals():
    """enable_mock_fallback=True 时，即使没有真实数据也返回 mock 航班。"""
    source = CtripSource(enable_mock_fallback=True)
    import asyncio
    results = asyncio.run(source.search_flights("PEK", "NRT", "2026-05-01", "2026-05-01"))

    assert len(results) > 0
    for r in results:
        assert "system_id" in r
        assert "origin_city" in r
        assert "destination_city" in r
        assert "confidence" in r
        assert "verdict" in r


def _install_fake_client(monkeypatch, *, flights, got_response):
    async def fake_worker(self, *args):
        if not got_response:
            raise CtripCollectionError()
        return flights

    async def no_retry_delay(fn, *args, **kwargs):
        return await fn(*args)

    monkeypatch.setattr(CtripSource, "_run_worker_once", fake_worker)
    monkeypatch.setattr(
        "backend.data_sources.ctrip_source.retry_with_backoff", no_retry_delay
    )


class _ImmediateWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, predicate):
        return True


class _FakeDriver:
    current_url = f"https://invalid.example/{SENSITIVE_SENTINEL}"
    title = SENSITIVE_SENTINEL

    def __init__(self, response_json):
        self.response_json = response_json
        self.page_load_timeout = None

    def set_page_load_timeout(self, timeout):
        self.page_load_timeout = timeout

    def get(self, url):
        return None

    def execute_script(self, script):
        if script.startswith("var r = window.__flightResponses"):
            return self.response_json
        return True


class _FailingDriver:
    def get(self, url):
        raise RuntimeError(SENSITIVE_SENTINEL)


def _real_client_with_responses(monkeypatch, responses):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _FakeDriver(json.dumps(responses))
    monkeypatch.setattr(ctrip_api, "WebDriverWait", _ImmediateWait)
    monkeypatch.setattr(ctrip_api.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(ctrip_api.random, "uniform", lambda low, high: 0)
    return ctrip_api, client


def _load_ctrip_api(monkeypatch):
    class FakeTimeoutException(Exception):
        pass

    class FakeWebDriverException(Exception):
        pass

    module_stubs = {
        "selenium": SimpleNamespace(),
        "selenium.webdriver": SimpleNamespace(),
        "selenium.webdriver.support": SimpleNamespace(),
        "selenium.webdriver.support.ui": SimpleNamespace(
            WebDriverWait=_ImmediateWait
        ),
        "selenium.common": SimpleNamespace(),
        "selenium.common.exceptions": SimpleNamespace(
            TimeoutException=FakeTimeoutException,
            WebDriverException=FakeWebDriverException,
        ),
        "config": SimpleNamespace(REQUEST_DELAY=0),
        "shared": SimpleNamespace(
            parse_datetime=lambda value: None,
            resolve_city=lambda code: code,
        ),
        "browser": SimpleNamespace(
            init_browser=lambda **kwargs: (None, None),
            close_browser=lambda driver, profile: None,
            BATCH_INTERCEPT_JS="",
        ),
    }
    for name, module in module_stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "ctrip_api", raising=False)
    return importlib.import_module("ctrip_api")
