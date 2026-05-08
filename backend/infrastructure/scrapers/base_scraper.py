from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScrapeQuery:
    origin: str
    destination: str
    depart_date: str


class _FakeBrowser:
    """Returned by _launch_browser when stub_playwright fixture is active."""

    class _FakePage:
        async def goto(self, url: str, **kwargs) -> None:
            pass

        async def wait_for_selector(self, selector: str, **kwargs) -> None:
            pass

        async def content(self) -> str:
            return "<html></html>"

    async def new_page(self) -> _FakePage:
        return self._FakePage()

    async def close(self) -> None:
        pass


_browser_factory = None


async def _launch_browser():
    """Launch a real Playwright browser, or return FakeBrowser in tests."""
    if _browser_factory is not None:
        return await _browser_factory()
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    return await pw.chromium.launch(headless=True)


class BaseScraper(ABC):
    platform: str

    @abstractmethod
    async def fetch(self, q: ScrapeQuery) -> list[dict]:
        """Fetch and normalize flight deals for the given query."""
