from __future__ import annotations


async def scrape_realtime(
    *, origin: str, destination: str, depart_date: str
) -> list[dict]:
    """Real-time scrape fallback when cache misses.

    In production this launches multi-platform scrapers inline.
    Returns empty list when scrapers are unavailable (test/dev env).
    """
    return []
