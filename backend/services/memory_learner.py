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
    async with session_factory() as db:
        from backend.memory.long_term import LongTermMemory
        ltm = LongTermMemory(db)
        await ltm.add_query(
            user_id=user_id,
            query_text=intent.get("raw_text", ""),
            intent={k: v for k, v in intent.items() if k != "raw_text"},
        )
        await db.commit()


async def learn_from_click(
    user_id: str,
    flight_data: dict[str, Any],
    session_factory,
) -> None:
    """点击航班后异步更新记忆偏好（budget/preferred_airlines）。"""
    if not session_factory:
        return
    async with session_factory() as db:
        from backend.memory.long_term import LongTermMemory
        ltm = LongTermMemory(db)

        await ltm.add_click(user_id=user_id, flight_data=flight_data)

        airline = flight_data.get("airline")
        if airline:
            recent_clicks = await ltm.get_recent_clicks(user_id, limit=20)
            airline_counts: dict[str, int] = {}
            for click in recent_clicks:
                clicked_airline = click.get("flight_data", {}).get("airline")
                if clicked_airline:
                    airline_counts[clicked_airline] = (
                        airline_counts.get(clicked_airline, 0) + 1
                    )

            prefs = await ltm.get_preferences(user_id) or {}
            current_airlines: list[str] = list(
                prefs.get("preferred_airlines") or []
            )
            for clicked_airline, count in airline_counts.items():
                if count >= 2 and clicked_airline not in current_airlines:
                    current_airlines.append(clicked_airline)

            if set(current_airlines) != set(
                prefs.get("preferred_airlines") or []
            ):
                await ltm.upsert_preferences(
                    user_id, {"preferred_airlines": current_airlines}
                )

        recent_clicks = await ltm.get_recent_clicks(user_id, limit=5)
        prices = [
            click.get("flight_data", {}).get("price")
            for click in recent_clicks
            if click.get("flight_data", {}).get("price")
        ]
        if len(prices) >= 3:
            median_price = int(statistics.median(prices))
            rounded = round(median_price / 10) * 10
            await ltm.upsert_preferences(user_id, {"budget": rounded})

        await db.commit()


async def learn_from_query_history(
    user_id: str,
    session_factory,
) -> None:
    """分析查询历史，推断 frequent_cities / constraints（PRD 5.5）。"""
    if not session_factory:
        return
    async with session_factory() as db:
        from backend.memory.long_term import LongTermMemory
        ltm = LongTermMemory(db)

        recent = await ltm.get_recent_queries(user_id, limit=30)
        prefs = await ltm.get_preferences(user_id) or {}
        updates: dict[str, Any] = {}

        dest_counts: dict[str, int] = {}
        for query in recent:
            destination = query.get("intent", {}).get("destination")
            city = _destination_city(destination)
            if city:
                dest_counts[city] = dest_counts.get(city, 0) + 1

        current_cities: list[str] = list(prefs.get("frequent_cities") or [])
        changed = False
        for city, count in dest_counts.items():
            if count >= 3 and city not in current_cities:
                current_cities.append(city)
                changed = True
        if changed:
            updates["frequent_cities"] = current_cities

        recent3 = recent[:3]
        if len(recent3) == 3:
            constraints: list[str] = list(prefs.get("constraints") or [])
            dep_times = [
                query.get("intent", {}).get("dep_time") for query in recent3
            ]
            if (
                "avoid_redeye" not in constraints
                and all(dep_times)
                and all(_dep_hour(dep_time) >= 6 for dep_time in dep_times)
            ):
                constraints.append("avoid_redeye")
                updates["constraints"] = constraints

        if updates:
            await ltm.upsert_preferences(user_id, updates)
            await db.commit()


def _destination_city(destination: Any) -> str | None:
    if isinstance(destination, str):
        return destination.strip() or None
    if isinstance(destination, dict):
        city = destination.get("city") or destination.get("iata_code")
        return city.strip() if isinstance(city, str) and city.strip() else None
    return None


def _dep_hour(dep_time: str) -> int:
    try:
        return int(dep_time.split(":")[0])
    except (ValueError, IndexError, AttributeError):
        return 0
