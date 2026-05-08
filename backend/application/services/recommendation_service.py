from __future__ import annotations

from backend.application.contracts.recommendations import RecCard, RecommendationsResponseDto
from backend.infrastructure.db.flight_cache import read_cached_deals
from backend.infrastructure.db.memory_repo import list_memories

HOT_ROUTES = [("BJS", "SYX"), ("SHA", "CTU"), ("CAN", "HGH")]


async def build_recommendations(user_id: str) -> RecommendationsResponseDto:
    mems = await list_memories(user_id)
    if not mems:
        cards = [
            RecCard(
                title=f"{o}-{d}",
                reason="热门航线",
                preview_deal={"price": 480, "platform": "ctrip"},
            )
            for (o, d) in HOT_ROUTES
        ]
        return RecommendationsResponseDto(personalized=False, cards=cards)

    routes = next((m.value for m in mems if m.field == "frequent_routes"), {})
    cards = []
    for key, _ in sorted(routes.items(), key=lambda kv: -kv[1])[:3]:
        o, d = key.split("-")
        deals = await read_cached_deals(origin=o, destination=d, depart_date="2026-05-08")
        preview = deals[0] if deals else {"price": 480, "platform": "ctrip"}
        cards.append(RecCard(title=key, reason="符合出行习惯", preview_deal=preview))
    if not cards:
        cards = [
            RecCard(
                title=f"{o}-{d}",
                reason="热门航线",
                preview_deal={"price": 480, "platform": "ctrip"},
            )
            for (o, d) in HOT_ROUTES
        ]
    return RecommendationsResponseDto(personalized=True, cards=cards)
