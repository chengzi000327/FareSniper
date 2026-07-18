"""
携程特价机票监测工具 - 携程航班搜索客户端
使用 Selenium 驱动 Chrome，通过拦截 XHR 响应获取真实航班数据
"""
import json
import time
import random
import logging
from collections.abc import Mapping
from typing import List, Dict

from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

from config import REQUEST_DELAY
from shared import parse_datetime
from browser import (
    init_browser, close_browser,
    BATCH_INTERCEPT_JS,
)

logger = logging.getLogger(__name__)

_SUCCESS_PROVIDER_CODES = {0, "0", 200, "200"}


class _CtripStructuralParseError(Exception):
    pass


class CtripBrowserError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Ctrip browser collection failed")


def _is_recognized_success_envelope(response) -> bool:
    """Accept the inventory shape used here plus repository success codes.

    Existing Ctrip parsing treats a mapping with ``data.flightItineraryList``
    as the success shape. When the provider includes ``code`` or ``status``,
    only the repository's established success conventions (0 or 200, numeric
    or string) are accepted.
    """
    if not isinstance(response, Mapping):
        return False
    payload = response.get("data")
    if not isinstance(payload, Mapping):
        return False
    if not isinstance(payload.get("flightItineraryList"), list):
        return False
    for field in ("code", "status"):
        if field in response and response[field] not in _SUCCESS_PROVIDER_CODES:
            return False
    return True


class CtripFlightClient:
    """携程航班搜索客户端"""

    LIST_URL_TPL = "https://flights.ctrip.com/online/list/oneway-{dcity}-{acity}?depdate={date}"
    PAGE_LOAD_WAIT = 12  # 等待页面加载和 API 响应的秒数
    PAGE_LOAD_TIMEOUT = 20

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self._tmp_profile_dir = None

    def init_session(self):
        """启动 Chrome 浏览器（使用统一的 browser 模块）"""
        try:
            self.driver, self._tmp_profile_dir = init_browser(
                headless=self.headless,
                intercept_js=BATCH_INTERCEPT_JS,
            )
            self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)
        except WebDriverException:
            logger.error("ctrip_browser_init_failed")
            raise

    def close(self):
        """安全关闭浏览器（使用 driver.quit() 而非 service.stop()）"""
        close_browser(self.driver, self._tmp_profile_dir)
        self.driver = None
        self._tmp_profile_dir = None

    def __enter__(self):
        self.init_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def discover_destinations(self, dep_city_code: str = "BJS") -> Dict[str, str]:
        """
        从携程自动发现出发城市的所有国内航线目的地
        通过访问携程国内频道页，拦截 fuzzySearch API 获取航线列表
        非北京出发时，先获取北京航线再排除自身作为候选
        Returns:
            {城市代码: 城市名} 的字典，如 {"SHA": "上海", "CAN": "广州"}
        """
        if not self.driver:
            self.init_session()

        logger.info(
            "ctrip_destination_discovery_started origin=%s", dep_city_code
        )
        destinations = {}

        try:
            self.driver.get("https://flights.ctrip.com/online/channel/domestic")
            time.sleep(10)

            # 提取 fuzzySearch 响应（该页面返回北京出发的所有国内航线）
            raw = self.driver.execute_script(
                "var r = window.__fuzzyResponses || []; window.__fuzzyResponses = []; return JSON.stringify(r);"
            )
            responses = json.loads(raw)
            logger.debug(
                "ctrip_destination_responses count=%d", len(responses)
            )

            # 收集所有国内航线城市
            all_cities = {}  # code -> name
            for body_str in responses:
                try:
                    data = json.loads(body_str)
                    routes = data.get("routes", [])
                    for route in routes:
                        arr = route.get("arriveCity", {})
                        if arr.get("isIntl", False):
                            continue
                        code = arr.get("code", "")
                        name = arr.get("name", "")
                        if code and name:
                            all_cities[code] = name
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            # 排除出发城市自身
            destinations = {c: n for c, n in all_cities.items() if c != dep_city_code}
            # 非北京出发时，把北京加入候选
            if dep_city_code != "BJS" and "BJS" not in destinations:
                destinations["BJS"] = "北京"

            logger.info(
                "ctrip_destination_discovery_complete count=%d",
                len(destinations),
            )

        except Exception:
            logger.warning(
                "ctrip_destination_discovery_failed origin=%s",
                dep_city_code,
            )

        return destinations

    def search_batch_search(
        self, dcity: str, acity: str, dcity_name: str, acity_name: str, date_str: str
    ) -> list[dict]:
        """Return only recognized batchSearch response envelopes."""
        if not self.driver:
            try:
                self.init_session()
            except WebDriverException:
                raise CtripBrowserError("dependency_error") from None

        url = self.LIST_URL_TPL.format(
            dcity=dcity.lower(), acity=acity.lower(), date=date_str
        )
        try:
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, self.PAGE_LOAD_WAIT).until(
                    lambda d: d.execute_script(
                        "return (window.__flightResponses && window.__flightResponses.length > 0)"
                    )
                )
            except TimeoutException:
                raise CtripBrowserError(self._page_state_error() or "timeout") from None

            time.sleep(2)
            raw = self.driver.execute_script(
                "var r = window.__flightResponses || []; window.__flightResponses = []; return JSON.stringify(r);"
            )
            responses = json.loads(raw)
        except CtripBrowserError:
            raise
        except (WebDriverException, json.JSONDecodeError, TypeError):
            raise CtripBrowserError("parse_error") from None

        if not isinstance(responses, list):
            raise CtripBrowserError("parse_error")
        if not responses:
            raise CtripBrowserError(self._page_state_error() or "timeout")

        payloads: list[dict] = []
        for body in responses:
            try:
                payload = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                continue
            if _is_recognized_success_envelope(payload):
                payloads.append(payload)
        if not payloads:
            raise CtripBrowserError(self._page_state_error() or "parse_error")
        return payloads

    def search_oneway(
        self, dcity: str, acity: str, dcity_name: str, acity_name: str, date_str: str
    ) -> tuple:
        """Legacy monitor adapter returning parsed rows and a success flag."""
        try:
            payloads = self.search_batch_search(
                dcity, acity, dcity_name, acity_name, date_str
            )
        except CtripBrowserError:
            return [], False

        flights = []
        for payload in payloads:
            try:
                flights.extend(self._parse_response(payload, dcity_name, acity_name, date_str))
            except _CtripStructuralParseError:
                return [], False
        delay = REQUEST_DELAY + random.uniform(0, 1)
        time.sleep(delay)
        return flights, True

    def _page_state_error(self) -> str | None:
        if not self.driver:
            return None
        text = " ".join(
            str(getattr(self.driver, attribute, ""))
            for attribute in ("current_url", "title", "page_source")
        ).lower()
        if "captcha" in text or "验证码" in text:
            return "captcha_required"
        if "login" in text or "登录" in text:
            return "login_required"
        return None

    def _parse_response(
        self, data: dict, dcity_name: str, acity_name: str, date_str: str
    ) -> List[Dict]:
        """解析 batchSearch API 响应"""
        flights = []

        fl_list = data.get("data", {}).get("flightItineraryList", [])
        if not fl_list:
            logger.debug("ctrip_parse_empty depart_date=%s", date_str)
            return flights

        no_price_list = 0
        no_cabin_y = 0
        no_valid_price = 0
        parse_error = 0

        for item in fl_list:
            try:
                # 航班基本信息 — 支持中转航班（flightList 可能有多段）
                seg = item.get("flightSegments", [{}])[0]
                fl_all = seg.get("flightList", [])
                if not fl_all:
                    parse_error += 1
                    continue

                first_fl = fl_all[0]
                last_fl = fl_all[-1]
                transfer_count = len(fl_all) - 1

                # 航班号：多段用 → 连接
                flight_nos = [f.get("flightNo", "") for f in fl_all if f.get("flightNo")]
                flight_no = "→".join(flight_nos)

                # 航司：去重合并
                airlines_seen = []
                for f in fl_all:
                    a = f.get("marketAirlineName", "")
                    if a and a not in airlines_seen:
                        airlines_seen.append(a)
                airline = "/".join(airlines_seen)

                # 出发/到达：取第一段出发、最后一段到达
                dep_time = first_fl.get("departureDateTime", "")
                arr_time = last_fl.get("arrivalDateTime", "")
                dep_airport = first_fl.get("departureAirportShortName", "")
                arr_airport = last_fl.get("arrivalAirportShortName", "")

                # 飞行耗时：各段 duration 之和
                fly_duration = sum(f.get("duration", 0) for f in fl_all)

                # 中转耗时：相邻段之间的等待时间
                transfer_time = 0
                transfer_cities = []
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

                # 找最低经济舱价格
                best_price = None
                price_list = item.get("priceList", [])
                if not price_list:
                    no_price_list += 1
                    continue

                has_cabin_y = False
                for p in price_list:
                    if p.get("cabin") != "Y":
                        continue
                    has_cabin_y = True

                    price = p.get("adultPrice", 0)
                    if price <= 0:
                        continue

                    # 从 priceUnitList 中获取折扣率
                    discount_rate = self._get_discount_rate(p)

                    if best_price is None or price < best_price["price"]:
                        best_price = {
                            "price": int(price),
                            "discount_rate": discount_rate,
                        }

                if not has_cabin_y:
                    no_cabin_y += 1
                    continue

                if not best_price:
                    no_valid_price += 1
                    continue

                rate = best_price["discount_rate"]
                if rate > 0:
                    disc_display = f"{rate * 10:.1f}折"
                else:
                    disc_display = "未知"

                flights.append({
                    "flight_number": flight_no,
                    "airline": airline,
                    "dep_city": dcity_name,
                    "arr_city": acity_name,
                    "dep_airport": dep_airport,
                    "arr_airport": arr_airport,
                    "dep_time": dep_time,
                    "arr_time": arr_time,
                    "duration": fly_duration,
                    "transfer_time": transfer_time,
                    "transfer_count": transfer_count,
                    "transfer_cities": transfer_cities,
                    "price": best_price["price"],
                    "discount_rate": round(rate, 2),
                    "discount_display": disc_display,
                    "date": date_str,
                })

            except (AttributeError, KeyError, TypeError, IndexError):
                parse_error += 1
                continue

        # 解析结果为空时输出诊断统计
        if not flights:
            logger.warning(
                "ctrip_parse_all_filtered depart_date=%s input_count=%d "
                "no_price_count=%d no_economy_count=%d "
                "no_valid_price_count=%d parse_error_count=%d",
                date_str,
                len(fl_list),
                no_price_list,
                no_cabin_y,
                no_valid_price,
                parse_error,
            )
        if parse_error == len(fl_list):
            raise _CtripStructuralParseError()

        return flights

    @staticmethod
    def _get_discount_rate(price_item: dict) -> float:
        """从价格项中提取折扣率"""
        try:
            units = price_item.get("priceUnitList", [])
            for u in units:
                seats = u.get("flightSeatList", [])
                for s in seats:
                    rate = s.get("discountRate", 0)
                    if rate > 0:
                        return float(rate)
        except (KeyError, TypeError, ValueError):
            pass
        return 0.0
