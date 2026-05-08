from __future__ import annotations

from backend.infrastructure.db.memory_repo import list_memories, upsert_memory


async def learn_from_search(
    user_id: str,
    *,
    origin: str,
    destination: str,
    depart_date: str,
    picked_price: int,
) -> None:
    rows = {m.field: m.value for m in await list_memories(user_id)}

    routes = rows.get("frequent_routes", {})
    key = f"{origin}-{destination}"
    routes[key] = routes.get(key, 0) + 1
    await upsert_memory(user_id, "frequent_routes", routes, source="learned")

    band = rows.get(
        "psychological_price_band", {"min": picked_price, "max": picked_price}
    )
    band["min"] = min(band["min"], picked_price)
    band["max"] = max(band["max"], picked_price)
    await upsert_memory(user_id, "psychological_price_band", band, source="learned")
