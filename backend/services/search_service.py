from __future__ import annotations

from typing import Any, Dict, List

from backend.tools.analyze_history import analyze_history
from backend.tools.compare_prices import compare_prices
from backend.tools.generate_signals import generate_signals
from backend.tools.match_preference import match_preference


class SearchService:
    def __init__(self, llm_client, memory_service, data_source_registry) -> None:
        self.llm_client = llm_client
        self.memory_service = memory_service
        self.data_source_registry = data_source_registry

    async def search(self, user_id: str, message: str) -> Dict[str, Any]:
        query = await self.llm_client.parse_intent(message)
        preferences = await self.memory_service.get_preferences_map(user_id)

        primary_source = self.data_source_registry.get("ctrip")
        flights = await primary_source.search_flights(
            origin=query["origin"],
            destination=query["destination"],
            date_start=query["date_start"],
            date_end=query["date_end"],
        )

        budget = query.get("budget")
        if budget is not None:
            flights = [flight for flight in flights if int(flight["price"]) <= int(budget) * 1.2]

        flights.sort(key=lambda flight: int(flight["price"]))

        comparison = compare_prices(flights)
        route = "{origin}-{destination}".format(origin=query["origin"], destination=query["destination"])
        history_prices = await primary_source.get_history_prices(route=route, days=90)
        history = analyze_history(history_prices, comparison.get("min_price"))
        preference = match_preference(flights, preferences, query)
        signals = generate_signals(comparison, history, preference)

        for flight in flights:
            flight["signals"] = list(signals[:2])

        recommendation = await self.llm_client.generate_recommendation(
            flights=flights,
            preferences=preferences,
            metrics={
                "comparison": comparison,
                "history": history,
                "preference": preference,
                "signals": signals,
            },
        )

        await self.memory_service.add_query_history(user_id, query)

        return {
            "query": query,
            "flights": flights,
            "comparison": {**comparison, **history},
            "preference": preference,
            "recommendation": recommendation,
            "metadata": {
                "source": primary_source.name,
                "result_count": len(flights),
                "fallback_mode": any(
                    flight.get("metadata", {}).get("source") == "mock_fallback" for flight in flights
                ),
            },
        }
