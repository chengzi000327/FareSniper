"""为探索页瀑布流注入演示用航班快照(成都/广州/厦门)。

线上 flight_snapshots 目前只有 BJS→SHA / BJS→SYX 两条路线的真实抓取数据,
导致探索页瀑布流只能出 2 张卡。本脚本为缺失的 3 条热门路线补一批
**结构合理的演示种子**(多航班 / 多平台价 / 带 90 天历史均价),让瀑布流铺满。

注意:这 3 条是构造数据,非真实抓取;真实爬虫跑通后会被同 dedup key 覆盖。

运行(项目根目录):
    PYTHONPATH=. python3 backend/scripts/seed_demo_snapshots.py
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv("backend/.env")  # 必须在 import backend.* 之前,供 DB engine 读取 DATABASE_URL

from backend.infrastructure.db.flight_snapshot_repo import upsert_flights  # noqa: E402

# dest_code -> (城市, [(航班号, 航司, 起飞, 到达, 时长, 基准价), ...], 90天均价, 90天最低)
ROUTES: dict[str, tuple[str, list[tuple[str, str, str, str, str, int]], int, int]] = {
    "CTU": (
        "成都",
        [
            ("CA1405", "中国国航", "08:20", "11:10", "2h50m", 520),
            ("3U8882", "四川航空", "12:30", "15:20", "2h50m", 780),
            ("CA1419", "中国国航", "16:00", "18:50", "2h50m", 1080),
            ("3U8888", "四川航空", "20:10", "23:00", "2h50m", 1280),
        ],
        950,
        480,
    ),
    "CAN": (
        "广州",
        [
            ("CZ3104", "中国南方航空", "07:50", "11:00", "3h10m", 580),
            ("CZ3108", "中国南方航空", "13:20", "16:30", "3h10m", 920),
            ("HU7802", "海南航空", "17:40", "20:50", "3h10m", 1260),
            ("CZ3112", "中国南方航空", "21:00", "23:55", "2h55m", 1480),
        ],
        1050,
        560,
    ),
    "XMN": (
        "厦门",
        [
            ("MF8102", "厦门航空", "09:10", "12:00", "2h50m", 460),
            ("MF8106", "厦门航空", "14:00", "16:50", "2h50m", 720),
            ("MF8110", "厦门航空", "18:30", "21:20", "2h50m", 980),
            ("MF8114", "厦门航空", "22:00", "23:55", "1h55m", 1100),
        ],
        780,
        440,
    ),
}
PLATFORMS = ["携程", "去哪儿", "飞猪"]


def _near_dates(n: int = 3) -> list[str]:
    today = date.today()
    return [(today + timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(n)]


def _build_flights() -> list[dict]:
    out: list[dict] = []
    for dest, (_city, flights, havg, hlow) in ROUTES.items():
        for day_idx, depart_date in enumerate(_near_dates()):
            for fno, airline, dep, arr, dur, base in flights:
                price = base + day_idx * 15  # 逐日微浮动,避免三天完全相同
                prices = [
                    {"platform": PLATFORMS[0], "price": price, "lowest": True, "url": ""},
                    {"platform": PLATFORMS[1], "price": price + 30, "lowest": False, "url": ""},
                    {"platform": PLATFORMS[2], "price": price + 55, "lowest": False, "url": ""},
                ]
                out.append(
                    {
                        "flight_no": fno,
                        "airline": airline,
                        "origin_code": "BJS",
                        "destination_code": dest,
                        "depart_date": depart_date,
                        "dep_time": dep,
                        "arr_time": arr,
                        "duration": dur,
                        "stops": 0,
                        "lowest_price": price,
                        "history_avg_90d": havg,
                        "history_low_90d": hlow,
                        "prices": prices,
                    }
                )
    return out


async def main() -> None:
    flights = _build_flights()
    await upsert_flights(flights)
    routes = ", ".join(f"BJS→{d}" for d in ROUTES)
    print(f"已注入 {len(flights)} 条航班快照({len(ROUTES)} 路线 × {len(_near_dates())} 天):{routes}")


if __name__ == "__main__":
    asyncio.run(main())
