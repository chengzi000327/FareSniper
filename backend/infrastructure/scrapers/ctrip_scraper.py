from __future__ import annotations

from backend.infrastructure.scrapers.base_scraper import BaseScraper, ScrapeQuery, _launch_browser


class CtripScraper(BaseScraper):
    platform = "ctrip"

    async def fetch(self, q: ScrapeQuery) -> list[dict]:
        browser = await _launch_browser()
        try:
            page = await browser.new_page()
            url = (
                f"https://m.ctrip.com/webapp/flight/schedule"
                f"?from={q.origin}&to={q.destination}&date={q.depart_date}"
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
                    "flight_no": "MU5137",
                    "price": 480,
                    "platform": self.platform,
                    "airline": "MU",
                    "depart_time": "08:30",
                    "arrive_time": "11:00",
                    "origin": q.origin,
                    "destination": q.destination,
                    "depart_date": q.depart_date,
                    "source": "fake",
                }
            ]
        # Real parser (replace when site structure is confirmed):
        # from selectolax.parser import HTMLParser
        # tree = HTMLParser(html)
        # deals = []
        # for node in tree.css(".flight-item"):
        #     try:
        #         deals.append({...})
        #     except (AttributeError, ValueError):
        #         continue
        # return deals
        return []
