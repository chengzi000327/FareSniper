import asyncio

from backend.workers.alert_checker import check_alerts_once
from backend.workers.notification_dispatcher import dispatch_notifications_once
from backend.workers.scheduler import build_scheduler


async def main():
    s = build_scheduler()
    s.add_job(check_alerts_once, "interval", minutes=15, id="alert_loop")
    s.add_job(
        dispatch_notifications_once,
        "interval",
        minutes=1,
        id="notification_dispatch",
        max_instances=1,
        coalesce=True,
    )
    s.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
