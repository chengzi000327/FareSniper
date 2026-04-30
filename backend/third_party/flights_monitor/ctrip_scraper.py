"""
携程机票爬虫 - 基于 BaseScraper 的适配版本
API: batchSearch (XHR/fetch)
"""
import json
import logging
from typing import List, Dict, Optional

from base_scraper import BaseScraper, make_flight
from shared import parse_datetime

logger = logging.getLogger(__name__)

_INTERCEPT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
(function() {
    window.__ctripFlightResponses = [];
    const origFetch = window.fetch;
    window.fetch = function() {
        return origFetch.apply(this, arguments).then(function(response) {
            var url = typeof arguments[0] === 'string' ? arguments[0] : (arguments[0] && arguments[0].url) || '';
            if (url.indexOf('batchSearch') !== -1) {
                response.clone().text().then(function(body) {
                    window.__ctripFlightResponses.push(body);
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
        if (this._url && this._url.indexOf('batchSearch') !== -1) {
            xhr.addEventListener('load', function() {
                try { window.__ctripFlightResponses.push(xhr.responseText); } catch(e) {}
            });
        }
        return origSend.apply(this, arguments);
    };
})();
"""


class CtripScraper(BaseScraper):
    """携程机票爬虫（BaseScraper 版）"""

    PLATFORM_NAME = "携程"
    INTERCEPT_JS = _INTERCEPT_JS
    PAGE_LOAD_WAIT = 12

    def build_search_url(self, dcity: str, acity: str, date_str: str) -> str:
        return (
            f"https://flights.ctrip.com/online/list/oneway-{dcity.lower()}-{acity.lower()}"
            f"?depdate={date_str}"
        )

    def wait_js_check(self) -> str:
        return "return !!(window.__ctripFlightResponses && window.__ctripFlightResponses.length > 0)"

    def extract_raw(self, driver) -> List[str]:
        raw = driver.execute_script(
            "var r = window.__ctripFlightResponses || [];"
            "window.__ctripFlightResponses = [];"
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
        fl_list = data.get("data", {}).get("flightItineraryList", [])

        for item in fl_list:
            try:
                seg = item.get("flightSegments", [{}])[0]
                fl_all = seg.get("flightList", [])
                if not fl_all:
                    continue

                first_fl = fl_all[0]
                last_fl = fl_all[-1]
                transfer_count = len(fl_all) - 1

                flight_nos = [f.get("flightNo", "") for f in fl_all if f.get("flightNo")]
                flight_no = "→".join(flight_nos)

                airlines_seen: List[str] = []
                for f in fl_all:
                    a = f.get("marketAirlineName", "")
                    if a and a not in airlines_seen:
                        airlines_seen.append(a)
                airline = "/".join(airlines_seen)

                dep_time = first_fl.get("departureDateTime", "")
                arr_time = last_fl.get("arrivalDateTime", "")
                dep_airport = first_fl.get("departureAirportShortName", "")
                arr_airport = last_fl.get("arrivalAirportShortName", "")
                fly_duration = sum(f.get("duration", 0) for f in fl_all)

                transfer_time = 0
                transfer_cities: List[str] = []
                for ti in range(len(fl_all) - 1):
                    cur_arr = fl_all[ti].get("arrivalDateTime", "")
                    nxt_dep = fl_all[ti + 1].get("departureDateTime", "")
                    t_city = fl_all[ti].get("arrivalAirportShortName", "")
                    if t_city:
                        transfer_cities.append(t_city)
                    t1 = parse_datetime(cur_arr)
                    t2 = parse_datetime(nxt_dep)
                    if t1 and t2:
                        transfer_time += max(0, int((t2 - t1).total_seconds() / 60))

                best_price: Optional[Dict] = None
                price_list = item.get("priceList", [])
                for p in price_list:
                    if p.get("cabin") != "Y":
                        continue
                    price = p.get("adultPrice", 0)
                    if price <= 0:
                        continue
                    discount_rate = _extract_discount_rate(p)
                    if best_price is None or price < best_price["price"]:
                        best_price = {"price": int(price), "discount_rate": discount_rate}

                if not best_price:
                    continue

                flights.append(make_flight(
                    flight_number=flight_no,
                    airline=airline,
                    dep_city=dcity_name,
                    arr_city=acity_name,
                    dep_airport=dep_airport,
                    arr_airport=arr_airport,
                    dep_time=dep_time,
                    arr_time=arr_time,
                    duration=fly_duration,
                    price=best_price["price"],
                    date_str=date_str,
                    platform=self.PLATFORM_NAME,
                    transfer_time=transfer_time,
                    transfer_count=transfer_count,
                    transfer_cities=transfer_cities,
                    discount_rate=best_price["discount_rate"],
                ))

            except (KeyError, TypeError, IndexError) as e:
                logger.debug("[%s] 解析单条航班失败: %s", self.PLATFORM_NAME, e)
                continue

        return flights


def _extract_discount_rate(price_item: dict) -> float:
    try:
        for u in price_item.get("priceUnitList", []):
            for s in u.get("flightSeatList", []):
                rate = s.get("discountRate", 0)
                if rate > 0:
                    return float(rate)
    except (KeyError, TypeError, ValueError):
        pass
    return 0.0
