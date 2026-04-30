"""记忆自动学习：异步从用户行为推断偏好（PRD 5.5）。"""
from __future__ import annotations

import statistics
from typing import Any


async def learn_from_search(
    user_id: str,
    intent: dict[str, Any],
    session_factory,
) -> None:
    """每次搜索后异步更新 query_history，不阻塞主流程。"""
    if not session_factory:
        return
    try:
        async with session_factory() as db:
            from backend.memory.long_term import LongTermMemory
            ltm = LongTermMemory(db)
            await ltm.add_query(
                user_id=user_id,
                query_text=intent.get("raw_text", ""),
                intent={k: v for k, v in intent.items() if k != "raw_text"},
            )
            await db.commit()
    except Exception:
        pass


async def learn_from_click(
    user_id: str,
    flight_data: dict[str, Any],
    session_factory,
) -> None:
    """点击航班后异步更新记忆偏好（budget/preferred_airlines）。"""
    if not session_factory:
        return
    try:
        async with session_factory() as db:
            from backend.memory.long_term import LongTermMemory
            ltm = LongTermMemory(db)

            # 记录点击
            await ltm.add_click(user_id=user_id, flight_data=flight_data)

            # 更新 preferred_airlines：同航司点击 ≥2 次 → 加入列表
            airline = flight_data.get("airline")
            if airline:
                recent_clicks = await ltm.get_recent_clicks(user_id, limit=20)
                airline_counts: dict[str, int] = {}
                for c in recent_clicks:
                    a = c.get("flight_data", {}).get("airline")
                    if a:
                        airline_counts[a] = airline_counts.get(a, 0) + 1

                prefs = await ltm.get_preferences(user_id) or {}
                current_airlines: list[str] = list(prefs.get("preferred_airlines") or [])
                for a, cnt in airline_counts.items():
                    if cnt >= 2 and a not in current_airlines:
                        current_airlines.append(a)

                if set(current_airlines) != set(prefs.get("preferred_airlines") or []):
                    await ltm.upsert_preferences(user_id, {"preferred_airlines": current_airlines})

            # 更新 budget：最近 5 次点击价格中位数
            recent_clicks = await ltm.get_recent_clicks(user_id, limit=5)
            prices = [
                c.get("flight_data", {}).get("price")
                for c in recent_clicks
                if c.get("flight_data", {}).get("price")
            ]
            if len(prices) >= 3:
                median_price = int(statistics.median(prices))
                rounded = round(median_price / 10) * 10
                await ltm.upsert_preferences(user_id, {"budget": rounded})

            await db.commit()
    except Exception:
        pass


async def learn_from_query_history(
    user_id: str,
    session_factory,
) -> None:
    """分析查询历史，推断 frequent_cities / constraints（PRD 5.5）。"""
    if not session_factory:
        return
    try:
        async with session_factory() as db:
            from backend.memory.long_term import LongTermMemory
            ltm = LongTermMemory(db)

            recent = await ltm.get_recent_queries(user_id, limit=30)
            prefs = await ltm.get_preferences(user_id) or {}
            updates: dict[str, Any] = {}

            # 目的地 ≥3 次 → 加入 frequent_cities
            dest_counts: dict[str, int] = {}
            for q in recent:
                dest = q.get("intent", {}).get("destination")
                if dest:
                    dest_counts[dest] = dest_counts.get(dest, 0) + 1

            current_cities: list[str] = list(prefs.get("frequent_cities") or [])
            changed = False
            for city, cnt in dest_counts.items():
                if cnt >= 3 and city not in current_cities:
                    current_cities.append(city)
                    changed = True
            if changed:
                updates["frequent_cities"] = current_cities

            # 连续 3 次查询出发时间 ≥ 06:00 → 推断 avoid_redeye
            recent3 = recent[:3]
            if len(recent3) == 3:
                constraints: list[str] = list(prefs.get("constraints") or [])
                if "avoid_redeye" not in constraints:
                    all_non_redeye = all(
                        _dep_hour(q.get("intent", {}).get("dep_time", "")) >= 6
                        for q in recent3
                        if q.get("intent", {}).get("dep_time")
                    )
                    if all_non_redeye:
                        constraints.append("avoid_redeye")
                        updates["constraints"] = constraints

            if updates:
                await ltm.upsert_preferences(user_id, updates)
                await db.commit()
    except Exception:
        pass


def _dep_hour(dep_time: str) -> int:
    try:
        return int(dep_time.split(":")[0])
    except (ValueError, IndexError, AttributeError):
        return 0
