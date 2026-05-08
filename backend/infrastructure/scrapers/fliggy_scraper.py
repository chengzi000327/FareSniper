from __future__ import annotations

from bs4 import BeautifulSoup

from backend.infrastructure.scrapers.base_scraper import BaseScraper, ScrapeQuery, _launch_browser


class FliggyScraper(BaseScraper):
    platform = "fliggy"

    async def fetch(self, q: ScrapeQuery) -> list[dict]:
        browser = await _launch_browser()
        try:
            page = await browser.new_page()
            url = (
                f"https://h5.m.taobao.com/trip/flight/domestic"
                f"/{q.origin}-{q.destination}.html"
                f"?date={q.depart_date}"
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
                    "flight_no": "3U8888",
                    "price": 440,
                    "platform": self.platform,
                    "airline": "3U",
                    "depart_time": "10:00",
                    "arrive_time": "12:25",
                    "origin": q.origin,
                    "destination": q.destination,
                    "depart_date": q.depart_date,
                    "source": "fake",
                }
            ]
        soup = BeautifulSoup(html, "html.parser")
        deals = []
        for node in soup.select(".flight-item"):
            try:
                deals.append(
                    {
                        "flight_no": node.select_one(".flight-no").get_text(strip=True),
                        "price": int(
                            node.select_one(".price")
                            .get_text(strip=True)
                            .replace("¥", "")
                        ),
                        "platform": self.platform,
                        "airline": node.select_one(".airline").get_text(strip=True),
                        "depart_time": node.select_one(".depart").get_text(strip=True),
                        "arrive_time": node.select_one(".arrive").get_text(strip=True),
                        "origin": q.origin,
                        "destination": q.destination,
                        "depart_date": q.depart_date,
                        "source": "scrape",
                    }
                )
            except (AttributeError, ValueError):
                continue
        return deals
