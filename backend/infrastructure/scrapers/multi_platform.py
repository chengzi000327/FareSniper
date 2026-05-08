from __future__ import annotations


async def scrape_all_routes() -> None:
    """Aggregate scrape across all platforms and write to flight_cache.

    Full implementation lives in TG-09l. This stub is a valid no-op so that
    the APScheduler job can register and fire without import errors.
    """
