"""
多平台机票聚合搜索
携程（稳定）+ 去哪儿 + 同程。飞猪/航旅纵横有强反爬，已移除。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Tuple, Type

from base_scraper import BaseScraper
from ctrip_scraper import CtripScraper
from qunar_scraper import QunarScraper
from tongcheng_scraper import TongchengScraper

logger = logging.getLogger(__name__)

# 默认启用的平台列表（可通过 enabled_platforms 参数覆盖）
# 飞猪（504/session crash）和航旅纵横（403）已确认封锁自动化，暂不启用
ALL_PLATFORMS: List[Type[BaseScraper]] = [
    CtripScraper,
    QunarScraper,
    TongchengScraper,
]


class MultiPlatformClient:
    """
    多平台聚合客户端。

    每个平台独立启动一个浏览器会话，顺序搜索（避免同时开多个 Chrome 耗尽内存）。
    结果按 (flight_number, dep_time) 去重——同一航班在不同平台出现时保留最低价。
    """

    def __init__(
        self,
        headless: bool = False,
        enabled_platforms: List[Type[BaseScraper]] | None = None,
    ) -> None:
        self.headless = headless
        self.platform_classes = enabled_platforms or ALL_PLATFORMS

    def search_oneway(
        self,
        dcity: str,
        acity: str,
        dcity_name: str,
        acity_name: str,
        date_str: str,
    ) -> Tuple[List[Dict], Dict[str, bool]]:
        """
        跨平台搜索单程航班。

        Returns:
            (flights, platform_status)
            flights: 合并去重后的航班列表（price 升序）
            platform_status: {平台名: 是否获取到有效响应}
        """
        all_flights: List[Dict] = []
        platform_status: Dict[str, bool] = {}

        for cls in self.platform_classes:
            platform_name = cls.PLATFORM_NAME
            logger.info("[多平台] 开始搜索 %s (%s->%s %s)", platform_name, dcity_name, acity_name, date_str)
            t0 = time.time()

            try:
                with cls(headless=self.headless) as scraper:
                    flights, got_response = scraper.search_oneway(
                        dcity, acity, dcity_name, acity_name, date_str
                    )
                elapsed = time.time() - t0
                platform_status[platform_name] = got_response
                all_flights.extend(flights)
                logger.info(
                    "[多平台] %s 完成: 获取 %d 条航班, 耗时 %.1fs",
                    platform_name, len(flights), elapsed,
                )
            except Exception as e:
                elapsed = time.time() - t0
                platform_status[platform_name] = False
                logger.warning(
                    "[多平台] %s 异常: %s (耗时 %.1fs)",
                    platform_name, e, elapsed,
                )

        merged = _merge_flights(all_flights)
        logger.info(
            "[多平台] 合并完成: 原始 %d 条 -> 去重后 %d 条 (涵盖 %d 个平台)",
            len(all_flights), len(merged), len(self.platform_classes),
        )
        return merged, platform_status


def _merge_flights(flights: List[Dict]) -> List[Dict]:
    """
    去重合并：同一航班（flight_number + dep_time）保留最低价。
    同一航班号不同平台来源时，price 取最低，其余字段取最低价记录。
    最终按 price 升序返回。
    """
    best: Dict[str, Dict] = {}
    for f in flights:
        key = f"{f.get('flight_number', '')}|{f.get('dep_time', '')}|{f.get('date', '')}"
        if key not in best or f["price"] < best[key]["price"]:
            best[key] = f
    return sorted(best.values(), key=lambda x: x["price"])


def search_multiplatform(
    dcity: str,
    acity: str,
    dcity_name: str,
    acity_name: str,
    date_str: str,
    headless: bool = False,
    enabled_platforms: List[Type[BaseScraper]] | None = None,
) -> Tuple[List[Dict], Dict[str, bool]]:
    """便捷函数：创建 MultiPlatformClient 并执行单次搜索。"""
    client = MultiPlatformClient(headless=headless, enabled_platforms=enabled_platforms)
    return client.search_oneway(dcity, acity, dcity_name, acity_name, date_str)
