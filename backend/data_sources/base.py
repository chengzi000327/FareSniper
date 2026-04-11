from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List


class DataSource(ABC):
    name: str = "unknown"
    enabled: bool = True

    @abstractmethod
    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, object]]:
        raise NotImplementedError

    @abstractmethod
    async def get_history_prices(self, route: str, days: int) -> List[Dict[str, object]]:
        raise NotImplementedError
