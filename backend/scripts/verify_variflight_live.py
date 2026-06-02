"""端到端验证：飞常准实时数据源真打 → 入 prod 库 → 查 flight_snapshots 确认真实数据。

只读 + 真实爬取一条路线，不改任何业务代码。运行：

    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
        backend/scripts/verify_variflight_live.py

链路：crawl_route → search_flights_with_status(真打飞常准) → normalize
      → upsert_flights → flight_snapshots / platform_price_snapshots 表。

入的是 DATABASE_URL 指向的**线上 prod 库**（真实爬取本就该入 prod）。
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

# 仓库根：backend/scripts/verify_variflight_live.py → 上三级。
ROOT = Path(__file__).resolve().parents[2]
# 显式 load_dotenv(backend/.env)（与 config.Settings 的 env_file 一致，双保险）。
load_dotenv(ROOT / "backend" / ".env")
# 确保 `import backend.*` 可解析。
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# config.settings 在 import 时即读取 backend/.env，故 load_dotenv 必须在 import 前。
from sqlalchemy import func, select  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.infrastructure.db.base import get_session  # noqa: E402
from backend.infrastructure.db.crawl_job_repo import get_crawl_job  # noqa: E402
from backend.infrastructure.db.flight_snapshot_repo import (  # noqa: E402
    FlightSnapshot,
    PlatformPriceSnapshot,
)
from backend.infrastructure.flight_data.variflight_client import (  # noqa: E402
    _mask_key,
)
from backend.infrastructure.scrapers.multi_platform import crawl_route  # noqa: E402

# 验证路线：BJS（北京）→ CTU（成都），明天。
ORIGIN = "BJS"
DESTINATION = "CTU"
DEPART_DATE = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")


def _line(char: str = "-", n: int = 72) -> None:
    print(char * n)


async def _count_rows() -> dict[str, int]:
    """统计该路线该日期的 flight_snapshots 行数 + variflight 平台价格行数。"""
    async with get_session() as s:
        snap_count = (
            await s.execute(
                select(func.count())
                .select_from(FlightSnapshot)
                .where(
                    FlightSnapshot.origin_code == ORIGIN,
                    FlightSnapshot.destination_code == DESTINATION,
                    FlightSnapshot.depart_date == DEPART_DATE,
                )
            )
        ).scalar_one()
        vf_price_count = (
            await s.execute(
                select(func.count())
                .select_from(PlatformPriceSnapshot)
                .join(
                    FlightSnapshot,
                    FlightSnapshot.id == PlatformPriceSnapshot.flight_snapshot_id,
                )
                .where(
                    FlightSnapshot.origin_code == ORIGIN,
                    FlightSnapshot.destination_code == DESTINATION,
                    FlightSnapshot.depart_date == DEPART_DATE,
                    PlatformPriceSnapshot.platform == "variflight",
                )
            )
        ).scalar_one()
    return {"snapshots": snap_count, "variflight_prices": vf_price_count}


async def _sample_rows(limit: int = 6) -> list[dict]:
    """取几条真实样例：航司/航班号/最低价/crawled_at + 是否有 variflight 平台价。"""
    async with get_session() as s:
        snaps = (
            (
                await s.execute(
                    select(FlightSnapshot)
                    .where(
                        FlightSnapshot.origin_code == ORIGIN,
                        FlightSnapshot.destination_code == DESTINATION,
                        FlightSnapshot.depart_date == DEPART_DATE,
                    )
                    .order_by(FlightSnapshot.lowest_price.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        out: list[dict] = []
        for snap in snaps:
            platforms = (
                (
                    await s.execute(
                        select(PlatformPriceSnapshot.platform).where(
                            PlatformPriceSnapshot.flight_snapshot_id == snap.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            out.append(
                {
                    "airline": snap.airline,
                    "flight_no": snap.flight_no,
                    "lowest_price": snap.lowest_price,
                    "crawled_at": snap.crawled_at,
                    "platforms": sorted(set(platforms)),
                }
            )
        return out


async def main() -> int:
    print("飞常准实时数据源端到端真入库验证")
    _line("=")
    api_key = settings.variflight_api_key
    db_url = settings.database_url
    # DB host 脱敏展示（确认指向 prod，不泄漏凭据）。
    db_host = ""
    if "@" in db_url:
        db_host = db_url.split("@", 1)[1].split("/", 1)[0]
    print(f"路线         : {ORIGIN} → {DESTINATION}  日期 {DEPART_DATE}")
    print(f"VARIFLIGHT_KEY: {_mask_key(api_key) or '<缺失!>'}")
    print(f"DATABASE     : prod @ {db_host or '<未配置 DATABASE_URL!>'}")
    _line()

    if not api_key:
        print("❌ VARIFLIGHT_API_KEY 缺失，无法真打飞常准。")
        return 1
    if not db_url:
        print("❌ DATABASE_URL 缺失，无法入库。")
        return 1

    # ── 入库前行数 ────────────────────────────────────────────────
    before = await _count_rows()
    print(
        f"入库前  flight_snapshots={before['snapshots']}  "
        f"variflight_prices={before['variflight_prices']}"
    )

    # ── 真打飞常准 + 走完整 crawl_route 入 prod 库 ────────────────
    # 该 sandbox 出站偶发瞬时断连（httpx 抛空消息异常），与业务代码无关。
    # 仅在「飞常准报 request_failed 且未落库」时做有限重试，避免假阴性；
    # 不修改任何业务代码，重试仅发生在验证脚本内。
    print("→ 真实爬取中（crawl_route → 飞常准网关 → upsert_flights）…")
    max_attempts = 4
    job_id = ""
    for attempt in range(1, max_attempts + 1):
        job_id = await crawl_route(
            origin=ORIGIN, destination=DESTINATION, depart_date=DEPART_DATE
        )
        job_chk = await get_crawl_job(job_id)
        vf_chk = (job_chk or {}).get("platform_status", {}).get("variflight", {})
        err = str(vf_chk.get("error") or "")
        transient = err.startswith("request_failed") or err.startswith("http_5")
        if not transient:
            if attempt > 1:
                print(f"  （第 {attempt} 次成功）")
            break
        print(
            f"  第 {attempt}/{max_attempts} 次遇瞬时出站断连 "
            f"(variflight error={err!r})，重试…"
        )
        await asyncio.sleep(2)
    print(f"  crawl job_id = {job_id}")

    # ── 入库后行数 ────────────────────────────────────────────────
    after = await _count_rows()
    print(
        f"入库后  flight_snapshots={after['snapshots']}  "
        f"variflight_prices={after['variflight_prices']}"
    )
    _line()

    # ── crawl_job status / platform_status ───────────────────────
    job = await get_crawl_job(job_id)
    vf_status: dict = {}
    if job:
        print(f"crawl_job.status        = {job['status']}")
        ps = job.get("platform_status") or {}
        vf_status = ps.get("variflight") or {}
        print(f"platform_status.variflight = {vf_status}")
        if job.get("error_message"):
            print(f"error_message           = {job['error_message']}")
    else:
        print("⚠️ 未查到 crawl_job 记录。")
    _line()

    # ── 真实数据样例 ─────────────────────────────────────────────
    samples = await _sample_rows()
    print("真实数据样例（航司 / 航班号 / 最低价 / crawled_at / 平台）:")
    if not samples:
        print("  （该路线该日期无快照行）")
    for r in samples:
        print(
            f"  {r['airline']:<8} {r['flight_no']:<8} "
            f"¥{r['lowest_price']:<6} {r['crawled_at']}  {r['platforms']}"
        )
    _line("=")

    # ── 结论判定 ─────────────────────────────────────────────────
    vf_ok = vf_status.get("status") == "ok"
    vf_persisted = int(vf_status.get("persisted_rows", 0) or 0)
    has_vf_data = after["variflight_prices"] > 0
    success = bool(job) and vf_ok and vf_persisted > 0 and has_vf_data

    if success:
        print(
            f"✅ 端到端真入库成功：variflight status=ok, "
            f"persisted_rows={vf_persisted}, "
            f"platform_price_snapshots(variflight)={after['variflight_prices']} 行（真实抓取）。"
        )
        rc = 0
    else:
        print("❌ 端到端验证未通过，逐项核对：")
        print(f"   - crawl_job 存在        : {bool(job)}")
        print(f"   - variflight status=ok  : {vf_ok}  (实际 {vf_status.get('status')!r})")
        print(f"   - persisted_rows > 0    : {vf_persisted > 0}  (实际 {vf_persisted})")
        print(f"   - 库里有 variflight 价  : {has_vf_data}  ({after['variflight_prices']} 行)")
        if vf_status.get("error"):
            print(f"   - variflight error      : {vf_status.get('error')}")
        rc = 1

    print()
    print(
        "⚠️ 提醒：本脚本验证的是【本地直连飞常准 + 入 prod 库】。Railway worker "
        "service 是否配了 VARIFLIGHT_API_KEY 需你自行在 Railway dashboard 确认"
        "（脚本无法访问 Railway）——否则线上定时爬取仍会因 missing_api_key 跳过飞常准。"
    )
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
