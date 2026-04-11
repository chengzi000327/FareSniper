from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class MemoryService:
    def __init__(self, memory_file: Path) -> None:
        self.memory_file = memory_file
        self._lock = asyncio.Lock()

    async def ensure_initialized(self) -> None:
        if self.memory_file.exists():
            return
        await asyncio.to_thread(self.memory_file.parent.mkdir, parents=True, exist_ok=True)
        await self._write_data({})

    async def get_memory(self, user_id: str) -> Dict[str, Any]:
        data = await self._read_data()
        user_data = data.get(user_id, self._default_user_record())
        return {
            "user_id": user_id,
            "preferences": self._format_preferences(
                user_data["preferences"],
                user_data.get("preference_meta", {}),
            ),
            "query_history": user_data["query_history"],
            "click_history": user_data["click_history"],
        }

    async def get_preferences_map(self, user_id: str) -> Dict[str, Any]:
        data = await self._read_data()
        user_data = data.get(user_id, self._default_user_record())
        return dict(user_data["preferences"])

    async def update_preference(self, user_id: str, field: str, value: Any, source: str) -> Dict[str, Any]:
        async with self._lock:
            data = await self._read_data()
            user_data = data.setdefault(user_id, self._default_user_record())
            user_data["preferences"][field] = value
            user_data["preference_meta"][field] = {
                "source": source,
                "updated_at": self._now(),
            }
            await self._write_data(data)
        return await self.get_memory(user_id)

    async def add_query_history(self, user_id: str, query: Dict[str, Any]) -> None:
        async with self._lock:
            data = await self._read_data()
            user_data = data.setdefault(user_id, self._default_user_record())
            history_item = {
                "query": query,
                "created_at": self._now(),
            }
            user_data["query_history"] = ([history_item] + user_data["query_history"])[:20]
            await self._write_data(data)

    async def add_click_history(self, user_id: str, flight_info: Dict[str, Any]) -> None:
        async with self._lock:
            data = await self._read_data()
            user_data = data.setdefault(user_id, self._default_user_record())
            history_item = {
                "flight_info": flight_info,
                "created_at": self._now(),
            }
            user_data["click_history"] = ([history_item] + user_data["click_history"])[:20]
            await self._write_data(data)

    async def _read_data(self) -> Dict[str, Any]:
        await self.ensure_initialized()

        def _read() -> Dict[str, Any]:
            with self.memory_file.open("r", encoding="utf-8") as file:
                return json.load(file)

        return await asyncio.to_thread(_read)

    async def _write_data(self, data: Dict[str, Any]) -> None:
        def _write() -> None:
            with self.memory_file.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

        await asyncio.to_thread(_write)

    def _format_preferences(self, preferences: Dict[str, Any], meta: Dict[str, Any]) -> Any:
        data = []
        for field, value in preferences.items():
            meta_value = meta.get(field, {})
            data.append(
                {
                    "field": field,
                    "value": value,
                    "source": meta_value.get("source", "manual"),
                    "updated_at": meta_value.get("updated_at", self._now()),
                }
            )
        return data

    def _default_user_record(self) -> Dict[str, Any]:
        return {
            "preferences": {
                "price_anchor": 600,
                "frequent_destinations": ["SYX", "KMG"],
                "preferred_cabin": "经济舱",
            },
            "preference_meta": {
                "price_anchor": {"source": "manual", "updated_at": self._now()},
                "frequent_destinations": {"source": "auto", "updated_at": self._now()},
                "preferred_cabin": {"source": "manual", "updated_at": self._now()},
            },
            "query_history": [],
            "click_history": [],
        }

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
