"""节假日判断（工程计算，写死 2026 年节假日列表）。"""
from __future__ import annotations

from datetime import date

HOLIDAY_RANGES_2026 = [
    ("2026-01-01", "2026-01-01"),  # 元旦
    ("2026-02-17", "2026-02-23"),  # 春节
    ("2026-04-04", "2026-04-06"),  # 清明
    ("2026-05-01", "2026-05-05"),  # 五一
    ("2026-06-19", "2026-06-21"),  # 端午
    ("2026-10-01", "2026-10-07"),  # 国庆/中秋
]


def is_holiday(date_str: str) -> bool:
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return False
    for start, end in HOLIDAY_RANGES_2026:
        if date.fromisoformat(start) <= d <= date.fromisoformat(end):
            return True
    return False
