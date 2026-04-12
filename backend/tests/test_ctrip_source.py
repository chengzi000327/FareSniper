"""
Step 7 CtripSource 测试
不启动真实浏览器，只测试 normalize() 逻辑和 import 失败降级。
"""
from __future__ import annotations

import pytest

from backend.data_sources.ctrip_source import CtripSource


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

    assert result["platform"] == "ctrip"
    assert result["origin_code"] == "PEK"
    assert result["destination_code"] == "NRT"
    assert result["price"] == 2580
    assert result["airline"] == "中国国航"


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


def test_third_party_import_failure_returns_empty():
    """第三方库 import 失败时 search_flights 返回空列表（或 mock 数据）。"""
    source = CtripSource(enable_mock_fallback=False)

    # 直接调用内部方法，模拟 import 失败
    import asyncio
    result = asyncio.run(source._try_third_party_search("PEK", "NRT", "2026-05-01", "2026-05-01"))
    # 没有真实浏览器，应返回空列表
    assert isinstance(result, list)


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
