from backend.infrastructure.db.promotion_repo import get_active_promotion


async def attach_promotion_signal(deal: dict) -> dict:
    p = await get_active_promotion(deal["platform"], deal["flight_no"], deal["depart_date"])
    if p:
        sigs = list(deal.get("signals", []))
        if "限时特卖" not in sigs:
            sigs.append("限时特卖")
        deal["signals"] = sigs
    return deal
