import re
from dataclasses import dataclass


@dataclass
class RefundRule:
    free_change_hours_before: int | None = None
    late_change_pct: int | None = None
    refund_after_depart: bool = True


def parse_refund(text: str) -> RefundRule:
    r = RefundRule()
    m = re.search(r"起飞前(\d+)小时.*免费", text)
    if m:
        r.free_change_hours_before = int(m.group(1))
    m = re.search(r"(\d+)\s*%\s*手续费", text)
    if m:
        r.late_change_pct = int(m.group(1))
    if "不可退" in text or "起飞后不可退票" in text:
        r.refund_after_depart = False
    return r
