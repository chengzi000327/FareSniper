"""当前日期工具:供 LLM prompt 注入"今天"以正确推算相对日期。

统一用 Asia/Shanghai 时区——Railway 容器跑 UTC,中国用户晚上的"今天"会比
UTC 早一天,直接用 date.today()/datetime.now() 会让 LLM 把"明天"算错一天。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_TZ = ZoneInfo("Asia/Shanghai")


def today_cn() -> str:
    """今天日期(北京时区),如 '2026年06月02日 周二'。"""
    now = datetime.now(_TZ)
    return f"{now.strftime('%Y年%m月%d日')} {_WEEKDAYS_CN[now.weekday()]}"
