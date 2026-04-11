from __future__ import annotations

from typing import Dict, List

from backend.data_sources.base import DataSource


class DataSourceRegistry:
    def __init__(self) -> None:
        self._sources: Dict[str, DataSource] = {}

    def register(self, source: DataSource) -> None:
        self._sources[source.name] = source

    def get(self, name: str) -> DataSource:
        return self._sources[name]

    def get_active(self) -> List[DataSource]:
        return [source for source in self._sources.values() if source.enabled]
