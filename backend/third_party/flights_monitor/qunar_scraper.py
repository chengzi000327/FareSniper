"""
去哪儿机票爬虫
API: /api/flight/search (JSON: data.data.flightLines[])
"""
import json
import logging
from typing import List, Dict, Optional

from base_scraper import BaseScraper, make_flight

logger = logging.getLogger(__name__)

_INTERCEPT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
(function() {
    window.__qunarFlightResponses = [];

    const _matchUrl = function(url) {
        return url && (
            url.indexOf('flight.qunar.com/api') !== -1 ||
            url.indexOf('contentapi.qunar.com') !== -1 ||
            url.indexOf('/flight/search') !== -1 ||
            url.indexOf('FlightOTA') !== -1
        );
    };

    const origFetch = window.fetch;
    window.fetch = function(input, init) {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        return origFetch.apply(this, arguments).then(function(response) {
            if (_matchUrl(url)) {
                response.clone().text().then(function(body) {
                    try {
                        var d = JSON.parse(body);
                        if (d && (d.data || d.ret)) {
                            window.__qunarFlightResponses.push(body);
                        }
                    } catch(e) {}
                });
            }
            return response;
        });
    };

    var origOpen = XMLHttpRequest.prototype.open;
    var origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
        this._url = url;
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
        var xhr = this;
        if (_matchUrl(this._url)) {
            xhr.addEventListener('load', function() {
                try {
                    var d = JSON.parse(xhr.responseText);
                    if (d && (d.data || d.ret)) {
                        window.__qunarFlightResponses.push(xhr.responseText);
                    }
                } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };
})();
"""


class QunarScraper(BaseScraper):
    """去哪儿机票爬虫"""

    PLATFORM_NAME = "去哪儿"
    INTERCEPT_JS = _INTERCEPT_JS
    PAGE_LOAD_WAIT = 15
    # 先访问主页获取 session cookie，否则搜索页会重定向到 404
    WARMUP_URL = "https://www.qunar.com"

    def build_search_url(self, dcity: str, acity: str, date_str: str) -> str:
        # 去哪儿机票搜索，不带 startSearch=true（会触发反爬重定向）
        return (
            f"https://flight.qunar.com/site/oneway_index.htm"
            f"?fromCode={dcity.upper()}"
            f"&toCode={acity.upper()}"
            f"&searchDepartDate={date_str}"
            f"&searchDepartureAirport={dcity.upper()}"
            f"&searchArrivalAirport={acity.upper()}"
        )

    def wait_js_check(self) -> str:
        return "return !!(window.__qunarFlightResponses && window.__qunarFlightResponses.length > 0)"

    def extract_raw(self, driver) -> List[str]:
        raw = driver.execute_script(
            "var r = window.__qunarFlightResponses || [];"
            "window.__qunarFlightResponses = [];"
            "return JSON.stringify(r);"
        )
        return json.loads(raw)

    def parse_raw(
        self, body_str: str, dcity_name: str, acity_name: str, date_str: str
    ) -> List[Dict]:
        data = self._safe_json(body_str)
        if not data:
            return []

        flights = []
        # 去哪儿响应结构：data.data.flightLines 或 data.flightLines
        flight_lines = (
            data.get("data", {}).get("flightLines")
            or data.get("flightLines")
            or []
        )

        for item in flight_lines:
            try:
                # 多段航班支持：flightList
                fl_all = item.get("flightList") or [item]
                first = fl_all[0]
                last = fl_all[-1]
                transfer_count = len(fl_all) - 1

                flight_no = "→".join(
                    f.get("flightNo", f.get("flightNumber", "")) for f in fl_all
                    if f.get("flightNo") or f.get("flightNumber")
                )
                airline = _first_nonempty(
                    item.get("airlineName"),
                    first.get("airlineName"),
                    first.get("marketAirlineName"),
                )
                dep_time = first.get("departTime") or first.get("depTime", "")
                arr_time = last.get("arrTime") or last.get("arrivalTime", "")
                dep_airport = first.get("departAirportName") or first.get("depAirport", "")
                arr_airport = last.get("arrAirportName") or last.get("arrAirport", "")

                # 飞行时长（分钟）
                duration = _to_minutes(
                    item.get("duration") or item.get("flyTime")
                    or sum(f.get("duration", 0) for f in fl_all)
                )

                # 中转
                transfer_time = _to_minutes(item.get("transferDuration", 0))
                transfer_cities = [
                    f.get("arrAirportName", "") for f in fl_all[:-1]
                    if f.get("arrAirportName")
                ]

                # 价格：priceList 或直接字段
                price, discount_rate = _extract_qunar_price(item)
                if price <= 0:
                    continue

                flights.append(make_flight(
                    flight_number=flight_no,
                    airline=airline or "",
                    dep_city=dcity_name,
                    arr_city=acity_name,
                    dep_airport=dep_airport,
                    arr_airport=arr_airport,
                    dep_time=dep_time,
                    arr_time=arr_time,
                    duration=duration,
                    price=price,
                    date_str=date_str,
                    platform=self.PLATFORM_NAME,
                    transfer_time=transfer_time,
                    transfer_count=transfer_count,
                    transfer_cities=transfer_cities,
                    discount_rate=discount_rate,
                ))

            except (KeyError, TypeError, IndexError) as e:
                logger.debug("[%s] 解析单条航班失败: %s", self.PLATFORM_NAME, e)
                continue

        return flights


# ── helpers ───────────────────────────────────────────────────────────────────

def _first_nonempty(*args) -> Optional[str]:
    for a in args:
        if a:
            return str(a)
    return None


def _to_minutes(val) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        # "2:30" → 150, "150" → 150
        if ":" in val:
            parts = val.split(":")
            try:
                return int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                pass
        try:
            return int(val)
        except ValueError:
            pass
    return 0


def _extract_qunar_price(item: dict):
    """提取去哪儿航班最低经济舱价格，返回 (price, discount_rate)"""
    # 尝试 priceList
    price_list = item.get("priceList") or item.get("prices") or []
    best_price = 0
    best_rate = 0.0
    for p in price_list:
        cabin = p.get("cabin", p.get("cabinClass", ""))
        if cabin and cabin not in ("Y", "Economy", "economy", "经济舱", ""):
            continue
        price = int(p.get("price") or p.get("adultPrice") or p.get("salePrice") or 0)
        if price <= 0:
            continue
        rate = float(p.get("discountRate") or p.get("discount") or 0)
        if best_price == 0 or price < best_price:
            best_price = price
            best_rate = rate

    if best_price > 0:
        return best_price, best_rate

    # 直接字段（部分响应简化结构）
    price = int(
        item.get("lowestPrice") or item.get("price") or item.get("adultPrice") or 0
    )
    rate = float(item.get("discountRate") or item.get("discount") or 0)
    return price, rate
