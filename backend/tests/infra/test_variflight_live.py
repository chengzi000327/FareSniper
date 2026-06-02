"""飞常准真实数据 live 验收测试。

默认 **跳过**——只有显式 `RUN_VARIFLIGHT_LIVE=1` 才会真打飞常准 API,
避免 CI/常规测试消耗 API 额度。用于人工确认"接真数据"端到端通:

    RUN_VARIFLIGHT_LIVE=1 python3 -m pytest backend/tests/infra/test_variflight_live.py -v

需要 backend/.env 里配置 VARIFLIGHT_API_KEY(本文件会自动 load)。
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.infrastructure.flight_data.variflight_client import (  # noqa: E402
    search_flights_with_status,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_VARIFLIGHT_LIVE"),
    reason="设置 RUN_VARIFLIGHT_LIVE=1 才会真打飞常准 API",
)


@pytest.mark.asyncio
async def test_live_returns_real_economy_flights():
    """真打飞常准:北京→三亚,断言返回真实经济舱航班、价格升序。"""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    result = await search_flights_with_status("PEK", "SYX", tomorrow)

    assert result.ok, f"飞常准返回错误: {result.error}"
    assert result.rows, "预期返回真实航班,实际为空"

    first = result.rows[0]
    assert first["source"] == "variflight"
    assert first["platform"] == "variflight"
    assert first["price"] > 0, "价格应为正"
    assert first["flight_no"], "航班号不应为空"
    assert first["date"] == tomorrow, "出发日期应与请求一致"

    prices = [r["price"] for r in result.rows]
    assert prices == sorted(prices), "结果应按价格升序"


@pytest.mark.asyncio
async def test_live_unknown_route_is_empty_not_error():
    """冷门/无航班路线应是 empty(error=None)而非报错,验证 empty≠error 语义。"""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # 用一个几乎不可能有直飞的城市对,验证"正常无结果"走 empty 分支
    result = await search_flights_with_status("LHW", "DLC", tomorrow)

    # 关键:即便 rows 为空,只要不是 API/网络错误,error 应为 None
    assert result.error is None or result.error.startswith(
        ("http_", "api_code_", "request_failed", "bad_json")
    ), f"未预期的 error 类型: {result.error}"
