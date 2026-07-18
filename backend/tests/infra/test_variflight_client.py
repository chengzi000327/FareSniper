"""飞常准 REST 直连客户端单测 — 全程 mock httpx,不真打飞常准 API(省 key 额度)。

覆盖：请求 URL / header(X-VARIFLIGHT-KEY) / body(endpoint+params+price_mode)构造,
以及响应解析(从 Y 舱取最低价、按价格升序排序)、非 200/异常时的静默回退语义。
"""
from __future__ import annotations

import httpx
import pytest

import backend.infrastructure.flight_data.variflight_client as vc


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json = json_body

    def json(self) -> dict:
        return self._json


def _sample_payload() -> dict:
    """仿真实结构：data 不按价格排序,cabins 含多舱位。"""
    return {
        "code": 200,
        "message": "Success",
        "data": [
            {
                "flightno": "CA1701",
                "flightcompany": "中国国航",
                "flightdepcode": "PEK",
                "flightarrcode": "SHA",
                "depaptccity": "北京",
                "arraptccity": "上海",
                "depdate": "2026-06-10",
                "stopflag": 0,
                "cabins": [
                    {"cabinclass": "Y", "price": 1280, "stprice": 0, "discount": 0.9},
                    {"cabinclass": "F", "price": 4200, "stprice": 0, "discount": 1.0},
                ],
            },
            {
                "flightno": "MU5137",
                "flightcompany": "东方航空",
                "flightdepcode": "PEK",
                "flightarrcode": "SHA",
                "depaptccity": "北京",
                "arraptccity": "上海",
                "depdate": "2026-06-10",
                "stopflag": 0,
                "cabins": [
                    # 同一航班多 Y 价,应取最低 (480)
                    {"cabinclass": "Y", "price": 620, "stprice": 0, "discount": 0.7},
                    {"cabinclass": "Y", "price": 480, "stprice": 0, "discount": 0.5},
                ],
            },
        ],
    }


@pytest.mark.asyncio
async def test_search_flights_builds_request_and_parses(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "KEYABCDEFGH1234", raising=False)

    captured: dict = {}

    async def _fake_post(self, url, *, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(200, _sample_payload())

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    rows = await vc.search_flights("PEK", "SHA", "2026-06-10")

    # --- 请求构造断言 ---
    assert captured["url"] == "https://mcp.variflight.com/api/v1/mcp/data"
    assert captured["headers"]["X-VARIFLIGHT-KEY"] == "KEYABCDEFGH1234"
    assert captured["headers"]["Content-Type"] == "application/json"
    body = captured["json"]
    assert body["endpoint"] == "getFlightPriceByCities"
    params = body["params"]
    # PEK → 城市码 BJS,SHA → SHA
    assert params["dep_city"] == "BJS"
    assert params["arr_city"] == "SHA"
    assert params["dep_date"] == "2026-06-10"
    assert params["price_mode"] == "lowest"

    # --- 响应解析断言：取 Y 舱最低价,按价格升序 ---
    assert [r["flight_no"] for r in rows] == ["MU5137", "CA1701"]
    assert rows[0]["price"] == 480  # MU5137 同舱多价取最低
    assert rows[1]["price"] == 1280  # CA1701 取 Y 舱(忽略 F 舱 4200)
    assert all(r["source"] == "variflight" for r in rows)
    assert rows[0]["platform"] == "variflight"


@pytest.mark.asyncio
async def test_search_flights_with_status_ok(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "KEYABCDEFGH1234", raising=False)

    async def _fake_post(self, url, *, json=None, headers=None):
        return _FakeResponse(200, _sample_payload())

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    result = await vc.search_flights_with_status("PEK", "SHA", "2026-06-10")
    assert result.ok
    assert result.error is None
    assert len(result.rows) == 2


@pytest.mark.asyncio
async def test_search_flights_http_non_200_returns_empty(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "KEYABCDEFGH1234", raising=False)

    async def _fake_post(self, url, *, json=None, headers=None):
        return _FakeResponse(429, {})

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    rows = await vc.search_flights("PEK", "SHA", "2026-06-10")
    assert rows == []

    result = await vc.search_flights_with_status("PEK", "SHA", "2026-06-10")
    assert result.rows == []
    assert result.error == "http_429"


@pytest.mark.asyncio
async def test_search_flights_api_code_error_returns_empty(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "KEYABCDEFGH1234", raising=False)

    async def _fake_post(self, url, *, json=None, headers=None):
        return _FakeResponse(200, {"code": 401, "message": "unauthorized", "data": []})

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    result = await vc.search_flights_with_status("PEK", "SHA", "2026-06-10")
    assert result.rows == []
    assert result.error == "api_code_401"


@pytest.mark.asyncio
async def test_search_flights_network_exception_returns_empty(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "KEYABCDEFGH1234", raising=False)

    async def _fake_post(self, url, *, json=None, headers=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    rows = await vc.search_flights("PEK", "SHA", "2026-06-10")
    assert rows == []

    result = await vc.search_flights_with_status("PEK", "SHA", "2026-06-10")
    assert result.rows == []
    assert result.error and result.error.startswith("request_failed")


@pytest.mark.asyncio
async def test_search_flights_missing_key_returns_empty(monkeypatch):
    monkeypatch.setattr(vc.settings, "variflight_api_key", "", raising=False)

    async def _fail_post(self, url, *, json=None, headers=None):
        raise AssertionError("不应在缺 key 时发起请求")

    monkeypatch.setattr(httpx.AsyncClient, "post", _fail_post)

    result = await vc.search_flights_with_status("PEK", "SHA", "2026-06-10")
    assert result.rows == []
    assert result.error == "missing_api_key"


def test_mask_key():
    assert vc._mask_key("KEYABCDEFGH1234") == "KEYA...1234"
    assert vc._mask_key("") == ""
    assert vc._mask_key("short") == "*****"


def test_catalog_converts_non_legacy_airport_to_variflight_city_code():
    assert vc._to_city_code("TFU") == "CTU"
    assert vc._to_city_code("DEJ") == "TEN"
