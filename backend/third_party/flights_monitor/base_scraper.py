"""
多平台机票爬虫 - 基类
所有平台 scraper 继承此类，统一浏览器生命周期管理和输出格式。
"""
import json
import logging
import os
import random
import time
from typing import List, Dict, Optional, Tuple

from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

from browser import init_browser, close_browser

logger = logging.getLogger(__name__)

# 统一输出字段（与 ctrip_api.py 的 _normalize 格式一致，新增 platform）
FLIGHT_KEYS = (
    "flight_number", "airline", "dep_city", "arr_city",
    "dep_airport", "arr_airport", "dep_time", "arr_time",
    "duration",        # 飞行分钟数（整数）
    "transfer_time",   # 中转等待分钟数
    "transfer_count",  # 中转次数
    "transfer_cities", # 中转城市列表
    "price",           # 成人经济舱最低价（元）
    "discount_rate",   # 折扣率 0.0~1.0（0 表示未知）
    "discount_display",# "6.5折" 或 "未知"
    "date",            # 出发日期 YYYY-MM-DD
    "platform",        # 数据来源平台名
)


def make_flight(
    flight_number: str,
    airline: str,
    dep_city: str,
    arr_city: str,
    dep_airport: str,
    arr_airport: str,
    dep_time: str,
    arr_time: str,
    duration: int,
    price: int,
    date_str: str,
    platform: str,
    transfer_time: int = 0,
    transfer_count: int = 0,
    transfer_cities: Optional[List[str]] = None,
    discount_rate: float = 0.0,
) -> Dict:
    """构造统一格式的航班字典。"""
    if discount_rate > 0:
        disc_display = f"{discount_rate * 10:.1f}折"
    else:
        disc_display = "未知"
    return {
        "flight_number": flight_number,
        "airline": airline,
        "dep_city": dep_city,
        "arr_city": arr_city,
        "dep_airport": dep_airport,
        "arr_airport": arr_airport,
        "dep_time": dep_time,
        "arr_time": arr_time,
        "duration": duration,
        "transfer_time": transfer_time,
        "transfer_count": transfer_count,
        "transfer_cities": transfer_cities or [],
        "price": price,
        "discount_rate": round(discount_rate, 2),
        "discount_display": disc_display,
        "date": date_str,
        "platform": platform,
    }


class BaseScraper:
    """
    机票爬虫基类。子类只需实现：
      - PLATFORM_NAME: str
      - INTERCEPT_JS: str   注入到 Chrome 的 JS 拦截脚本
      - PAGE_LOAD_WAIT: int  等待API响应的超时秒数
      - build_search_url(dcity, acity, date_str) -> str
      - wait_js_check() -> str  告知基类如何判断"API响应已到达"
      - extract_raw(driver) -> List[str]  从 window 变量里取出响应字符串列表
      - parse_raw(body_str, dcity_name, acity_name, date_str) -> List[Dict]
    """
    PLATFORM_NAME: str = "unknown"
    INTERCEPT_JS: str = ""
    PAGE_LOAD_WAIT: int = 15
    REQUEST_DELAY: float = 4.0

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self.driver = None
        self._tmp_profile_dir = None

    # ── Context manager ───────────────────────────────────────────────────

    def __enter__(self):
        self.init_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    # 子类可设置预热 URL，在搜索前先访问该页面以获取 session cookie
    WARMUP_URL: Optional[str] = None

    def init_session(self) -> None:
        try:
            self.driver, self._tmp_profile_dir = init_browser(
                headless=self.headless,
                intercept_js=self.INTERCEPT_JS,
            )
        except WebDriverException as e:
            logger.error("[%s] 浏览器启动失败: %s", self.PLATFORM_NAME, e)
            raise
        if self.WARMUP_URL:
            try:
                logger.debug("[%s] 预热访问: %s", self.PLATFORM_NAME, self.WARMUP_URL)
                self.driver.get(self.WARMUP_URL)
                time.sleep(3)
            except Exception as e:
                logger.debug("[%s] 预热失败（忽略）: %s", self.PLATFORM_NAME, e)

    def close(self) -> None:
        close_browser(self.driver, self._tmp_profile_dir)
        self.driver = None
        self._tmp_profile_dir = None

    # ── Public API ────────────────────────────────────────────────────────

    def search_oneway(
        self,
        dcity: str,
        acity: str,
        dcity_name: str,
        acity_name: str,
        date_str: str,
    ) -> Tuple[List[Dict], bool]:
        """搜索单程航班，返回 (航班列表, 是否收到有效API响应)。"""
        if not self.driver:
            self.init_session()

        url = self.build_search_url(dcity, acity, date_str)
        flights: List[Dict] = []
        got_response = False

        try:
            logger.debug("[%s] 访问: %s", self.PLATFORM_NAME, url)
            self.driver.get(url)

            intercepted = False
            try:
                WebDriverWait(self.driver, self.PAGE_LOAD_WAIT).until(
                    lambda d: d.execute_script(self.wait_js_check())
                )
                intercepted = True
            except TimeoutException:
                logger.warning(
                    "[%s] 等待响应超时: %s->%s %s",
                    self.PLATFORM_NAME, dcity_name, acity_name, date_str,
                )

            time.sleep(2)
            raw_list = self.extract_raw(self.driver)

            if not raw_list:
                page_title = self.driver.title
                page_url = self.driver.current_url
                logger.warning(
                    "[%s] 未拦截到响应 | 拦截器触发=%s | 标题='%s' | URL=%s",
                    self.PLATFORM_NAME, intercepted, page_title, page_url,
                )
            else:
                got_response = True
                logger.debug("[%s] 拦截到 %d 个响应", self.PLATFORM_NAME, len(raw_list))

            for body_str in raw_list:
                try:
                    parsed = self.parse_raw(body_str, dcity_name, acity_name, date_str)
                    flights.extend(parsed)
                except Exception as e:
                    logger.warning(
                        "[%s] 响应解析异常: %s | 前200字符: %s",
                        self.PLATFORM_NAME, e, body_str[:200],
                    )

            if not flights and raw_list:
                self._save_debug(raw_list[0], date_str)

        except Exception as e:
            logger.warning(
                "[%s] 搜索失败 %s->%s %s: %s",
                self.PLATFORM_NAME, dcity_name, acity_name, date_str, e,
            )

        time.sleep(self.REQUEST_DELAY + random.uniform(0, 1))
        return flights, got_response

    # ── Abstract interface ────────────────────────────────────────────────

    def build_search_url(self, dcity: str, acity: str, date_str: str) -> str:
        raise NotImplementedError

    def wait_js_check(self) -> str:
        raise NotImplementedError

    def extract_raw(self, driver) -> List[str]:
        raise NotImplementedError

    def parse_raw(
        self, body_str: str, dcity_name: str, acity_name: str, date_str: str
    ) -> List[Dict]:
        raise NotImplementedError

    # ── Helpers ───────────────────────────────────────────────────────────

    def _save_debug(self, body_str: str, date_str: str) -> None:
        debug_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f".debug_{self.PLATFORM_NAME}_{date_str}.json",
        )
        if not os.path.exists(debug_file):
            try:
                data = json.loads(body_str) if isinstance(body_str, str) else body_str
                with open(debug_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info("[%s] 已保存调试响应到 %s", self.PLATFORM_NAME, debug_file)
            except Exception:
                pass

    @staticmethod
    def _safe_json(text: str) -> Optional[dict]:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
