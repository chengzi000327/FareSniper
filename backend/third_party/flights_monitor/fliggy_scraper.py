"""
飞猪（阿里旅行）机票爬虫
域名: www.fliggy.com
API: /flightindex.htm 触发 mtop.trip.flight.search.* 接口
"""
import json
import logging
from typing import List, Dict

from base_scraper import BaseScraper, make_flight

logger = logging.getLogger(__name__)

_INTERCEPT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
(function() {
    window.__fliggyFlightResponses = [];

    const _matchUrl = function(url) {
        return url && (
            url.indexOf('fliggy.com') !== -1 ||
            url.indexOf('alitrip.com') !== -1 ||
            url.indexOf('taobao.com') !== -1
        ) && (
            url.indexOf('flight') !== -1 ||
            url.indexOf('Flight') !== -1 ||
            url.indexOf('mtop') !== -1
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
                        if (d && (d.data || d.result || d.ret)) {
                            window.__fliggyFlightResponses.push(body);
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
                    if (d && (d.data || d.result || d.ret)) {
                        window.__fliggyFlightResponses.push(xhr.responseText);
                    }
                } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };
})();
"""


class FliggyScraper(BaseScraper):
    """飞猪机票爬虫"""

    PLATFORM_NAME = "飞猪"
    INTERCEPT_JS = _INTERCEPT_JS
    PAGE_LOAD_WAIT = 18  # 飞猪页面加载较慢

    def build_search_url(self, dcity: str, acity: str, date_str: str) -> str:
        return (
            f"https://www.fliggy.com/flightindex.htm"
            f"?depCity={dcity.upper()}&arrCity={acity.upper()}"
            f"&depDate={date_str}&cabin=Y&tripType=OW"
        )

    def wait_js_check(self) -> str:
        return "return !!(window.__fliggyFlightResponses && window.__fliggyFlightResponses.length > 0)"

    def extract_raw(self, driver) -> List[str]:
        raw = driver.execute_script(
            "var r = window.__fliggyFlightResponses || [];"
            "window.__fliggyFlightResponses = [];"
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
        # 飞猪阿里旅行 mtop 接口外层通常是 {"ret":["SUCCESS::..."],"data":{...}}
        # 实际航班列表深度不一，多路径尝试
        inner = (
            data.get("data") or data.get("result") or {}
        )
        if isinstance(inner, str):
            inner = self._safe_json(inner) or {}

        flight_list = (
            inner.get("flightList")
            or inner.get("flights")
            or inner.get("flightInfoList")
            or inner.get("data", {}).get("flightList")
            or []
        )

        for item in flight_list:
            try:
                segs = item.get("flightSegments") or item.get("segments") or [item]
                first = segs[0]
                last = segs[-1]
                transfer_count = len(segs) - 1

                flight_no = "→".join(
                    s.get("flightNo", s.get("flightNumber", "")) for s in segs
                    if s.get("flightNo") or s.get("flightNumber")
                )
                airline = (
                    item.get("airlineName")
                    or first.get("airlineName")
                    or first.get("carrierName", "")
                )
                dep_time = (
                    first.get("depTime") or first.get("departureTime")
                    or first.get("depDateTime", "")
                )
                arr_time = (
                    last.get("arrTime") or last.get("arrivalTime")
                    or last.get("arrDateTime", "")
                )
                dep_airport = (
                    first.get("depAirportName") or first.get("departureAirportName", "")
                )
                arr_airport = (
                    last.get("arrAirportName") or last.get("arrivalAirportName", "")
                )
                duration = _to_minutes(
                    item.get("duration") or item.get("flyDuration")
                    or sum(s.get("duration", 0) for s in segs)
                )
                transfer_time = _to_minutes(item.get("stopDuration", 0))
                transfer_cities = [
                    s.get("arrAirportName", "") for s in segs[:-1]
                    if s.get("arrAirportName")
                ]

                price, discount_rate = _extract_fliggy_price(item)
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


def _to_minutes(val) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
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


def _extract_fliggy_price(item: dict):
    """提取飞猪最低经济舱价格，返回 (price, discount_rate)"""
    price_list = (
        item.get("priceList") or item.get("prices")
        or item.get("fareList") or item.get("cabinList") or []
    )
    best_price = 0
    best_rate = 0.0
    for p in price_list:
        cabin = str(p.get("cabin") or p.get("cabinClass") or p.get("cabinType") or "Y")
        if cabin.upper() not in ("Y", "ECONOMY", ""):
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

    price = int(
        item.get("lowestPrice") or item.get("price")
        or item.get("adultPrice") or item.get("salePrice") or 0
    )
    rate = float(item.get("discountRate") or item.get("discount") or 0)
    return price, rate
