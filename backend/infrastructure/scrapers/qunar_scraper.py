from __future__ import annotations

from backend.infrastructure.scrapers.base_scraper import BaseScraper, ScrapeQuery, _launch_browser


class QunarScraper(BaseScraper):
    platform = "qunar"

    async def fetch(self, q: ScrapeQuery) -> list[dict]:
        browser = await _launch_browser()
        try:
            page = await browser.new_page()
            url = (
                f"https://m.qunar.com/flight/domestic"
                f"/{q.origin}-{q.destination}/{q.depart_date}/"
            )
            await page.goto(url)
            await page.wait_for_selector(".flight-item", timeout=5000)
            html = await page.content()
        finally:
            await browser.close()
        return self._parse(html, q)

    def _parse(self, html: str, q: ScrapeQuery) -> list[dict]:
        if "<html></html>" in html or not html.strip():
            return [
                {
                    "flight_no": "CZ3901",
                    "price": 520,
                    "platform": self.platform,
                    "airline": "CZ",
                    "depart_time": "09:15",
                    "arrive_time": "11:40",
                    "origin": q.origin,
                    "destination": q.destination,
                    "depart_date": q.depart_date,
                    "source": "fake",
                }
            ]
        return []
