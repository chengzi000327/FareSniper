import asyncio

from backend.workers.alert_checker import check_alerts_once
from backend.workers.scheduler import build_scheduler


async def main():
    s = build_scheduler()
    s.add_job(check_alerts_once, "interval", minutes=15, id="alert_loop")
    s.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
