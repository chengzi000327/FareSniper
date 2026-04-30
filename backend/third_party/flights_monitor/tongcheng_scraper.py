"""
同程旅行机票爬虫
同程为 Nuxt.js SSR 应用，航班数据在 window.__NUXT__.state.book1.flightLists
不需要 JS API 拦截，直接读取 SSR 数据。
"""
import json
import logging
from typing import List, Dict

from base_scraper import BaseScraper, make_flight

logger = logging.getLogger(__name__)

# 仅做反自动化规避，不需要 API 拦截
_STEALTH_JS = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"


class TongchengScraper(BaseScraper):
    """同程旅行机票爬虫（Nuxt SSR 数据提取）"""

    PLATFORM_NAME = "同程"
    INTERCEPT_JS = _STEALTH_JS
    PAGE_LOAD_WAIT = 20
    WARMUP_URL = "https://www.ly.com"

    def build_search_url(self, dcity: str, acity: str, date_str: str) -> str:
        return (
            f"https://www.ly.com/flights/itinerary/oneway/{dcity.upper()}-{acity.upper()}"
            f"?date={date_str}&cabin=Y"
        )

    def wait_js_check(self) -> str:
        # 同程为 Nuxt SSR，数据在 window.__NUXT__.state.book1.flightLists
        return (
            "try {"
            "  var fl = window.__NUXT__ && window.__NUXT__.state && "
            "           window.__NUXT__.state.book1 && "
            "           window.__NUXT__.state.book1.flightLists;"
            "  return !!(fl && fl.length > 0);"
            "} catch(e) { return false; }"
        )

    def extract_raw(self, driver) -> List[str]:
        raw = driver.execute_script(
            "try {"
            "  var fl = window.__NUXT__.state.book1.flightLists;"
            "  return fl ? JSON.stringify(fl) : '[]';"
            "} catch(e) { return '[]'; }"
        )
        # 返回单个 JSON 字符串（整个 flightLists），parse_raw 会处理数组
        flights_list = json.loads(raw)
        if flights_list:
            return [json.dumps(flights_list)]
        return []

    def parse_raw(
        self, body_str: str, dcity_name: str, acity_name: str, date_str: str
    ) -> List[Dict]:
        # extract_raw 返回的是 window.__NUXT__.state.book1.flightLists 数组
        flight_list = self._safe_json(body_str)
        if not isinstance(flight_list, list):
            return []

        flights = []
        for item in flight_list:
            try:
                price = int(item.get("lcp") or 0)
                if price <= 0:
                    continue

                # fRate 是价格百分比（如 40.00 = 4折）
                f_rate = float(item.get("fRate") or 100)
                discount_rate = f_rate / 100.0

                flight_no = item.get("flightNo", "")
                airline = item.get("airCompanyName", "")
                dep_time = item.get("flyOffOnlyTime", "")
                arr_time = item.get("arrivalOnlyTime", "")
                dep_airport = item.get("oapname", "") or item.get("originAirportShortName", "")
                arr_airport = item.get("aapname", "") or item.get("arriveAirportShortName", "")
                stop_num = int(item.get("stopNum") or 0)
                duration = _spantime_to_minutes(item.get("spantime", ""))

                flights.append(make_flight(
                    flight_number=flight_no,
                    airline=airline,
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
                    transfer_time=0,
                    transfer_count=stop_num,
                    transfer_cities=[],
                    discount_rate=discount_rate,
                ))

            except (KeyError, TypeError, IndexError, ValueError) as e:
                logger.debug("[%s] 解析单条航班失败: %s", self.PLATFORM_NAME, e)
                continue

        return flights


def _spantime_to_minutes(spantime: str) -> int:
    """解析同程飞行时长字符串，如 '3小时10分钟' → 190"""
    import re
    m = re.search(r"(\d+)小时", spantime)
    s = re.search(r"(\d+)分钟", spantime)
    hours = int(m.group(1)) if m else 0
    mins = int(s.group(1)) if s else 0
    return hours * 60 + mins
