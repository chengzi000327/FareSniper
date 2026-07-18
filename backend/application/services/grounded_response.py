"""Build deterministic response text from a frozen final deal snapshot."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence


_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:[¥￥$€£]\s*\d|\b[A-Z]{3}\s*\d|\d(?:[\d,.]*\d)?\s*(?:元|人民币))",
    re.IGNORECASE,
)
_PRICE_OR_BUDGET_CLAIM_RE = re.compile(
    r"(?:价格|票价|低价|均价|折扣|便宜|预算|税费|行李费)"
)
_FLIGHT_NUMBER_RE = re.compile(
    r"(?<![A-Z0-9])(?:[A-Z0-9]{2})\s?\d{3,4}(?![A-Z0-9])",
    re.IGNORECASE,
)
_TIME_RE = re.compile(
    r"(?<!\d)(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}月\d{1,2}日|"
    r"(?:[01]?\d|2[0-3]):[0-5]\d|(?:[01]?\d|2[0-3])点(?:[0-5]?\d分)?)(?!\d)"
)
_INELIGIBLE_PROVIDER_STATUSES = {
    "disabled",
    "empty",
    "error",
    "loading",
    "queued",
    "timeout",
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, frozenset)):
        return [_thaw(item) for item in value]
    return value


def _currency(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if len(normalized) == 3 and normalized.isalpha() else None


def _numeric_price(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value >= 0 else None


def _primary_currency(deals: Sequence[Mapping[str, Any]]) -> str:
    for deal in deals:
        normalized = _currency(deal.get("currency"))
        if normalized:
            return normalized
        for price in deal.get("prices") or ():
            if isinstance(price, Mapping):
                normalized = _currency(price.get("currency"))
                if normalized:
                    return normalized
    return "CNY"


def _display_price(deal: Mapping[str, Any], currency: str) -> int | None:
    deal_currency = _currency(deal.get("currency")) or currency
    if deal_currency == currency:
        for key in ("display_price", "price", "total_price", "lowest_price"):
            price = _numeric_price(deal.get(key))
            if price is not None:
                return price

    nested: list[int] = []
    for item in deal.get("prices") or ():
        if not isinstance(item, Mapping):
            continue
        if item.get("provider_status") in _INELIGIBLE_PROVIDER_STATUSES:
            continue
        if (_currency(item.get("currency")) or currency) != currency:
            continue
        price = _numeric_price(item.get("price"))
        if price is not None:
            nested.append(price)
    return min(nested) if nested else None


def _has_stale_price(deal: Mapping[str, Any]) -> bool:
    if deal.get("data_freshness") == "stale":
        return True
    for item in deal.get("prices") or ():
        if not isinstance(item, Mapping) or _numeric_price(item.get("price")) is None:
            continue
        if (
            item.get("data_freshness") == "stale"
            or item.get("price_status") == "stale"
            or item.get("provider_status") == "stale"
        ):
            return True
    return False


@dataclass(frozen=True, slots=True)
class ResponseRow:
    flight_no: str
    depart_time: str
    arrive_time: str
    display_price: int | None
    currency: str
    is_stale: bool
    card: Mapping[str, Any] = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ResponseFacts:
    rows: tuple[ResponseRow, ...]
    best_deal: ResponseRow | None
    minimum_display_price: int | None
    currency: str
    budget: int | None
    within_budget: bool | None
    has_stale_prices: bool

    @property
    def min_display_price(self) -> int | None:
        return self.minimum_display_price

    @property
    def stale(self) -> bool:
        return self.has_stale_prices

    def card_deals(self) -> list[dict[str, Any]]:
        return [_thaw(row.card) for row in self.rows]


def build_response_facts(
    deals: Sequence[Mapping[str, Any]], budget: int | None, limit: int = 7
) -> ResponseFacts:
    """Freeze the final deal order and derive every response claim from it."""
    if limit < 0:
        raise ValueError("limit must be non-negative")

    snapshot = [copy.deepcopy(dict(deal)) for deal in deals[:limit]]
    currency = _primary_currency(snapshot)
    rows = tuple(
        ResponseRow(
            flight_no=str(deal.get("flight_no") or "待确认"),
            depart_time=str(deal.get("depart_time") or "待确认"),
            arrive_time=str(deal.get("arrive_time") or "待确认"),
            display_price=_display_price(deal, currency),
            currency=_currency(deal.get("currency")) or currency,
            is_stale=_has_stale_price(deal),
            card=_freeze(deal),
        )
        for deal in snapshot
    )
    eligible_prices = [
        row.display_price
        for row in rows
        if row.currency == currency and row.display_price is not None
    ]
    minimum = min(eligible_prices) if eligible_prices else None
    normalized_budget = _numeric_price(budget)
    within_budget = (
        minimum <= normalized_budget
        if minimum is not None and normalized_budget is not None
        else None
    )
    return ResponseFacts(
        rows=rows,
        best_deal=rows[0] if rows else None,
        minimum_display_price=minimum,
        currency=currency,
        budget=normalized_budget,
        within_budget=within_budget,
        has_stale_prices=any(row.is_stale for row in rows),
    )


def _format_price(price: int | None, currency: str, *, code: bool = False) -> str:
    if price is None:
        return "待确认"
    if currency == "CNY":
        return f"¥{price}（CNY {price}）" if code else f"¥{price}"
    return f"{currency} {price}"


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def render_flight_markdown(facts: ResponseFacts) -> str:
    """Render headings, table, recommendation, and alerts from response facts."""
    lines = [f"### 航班结果（{len(facts.rows)}）", ""]
    lines.extend(
        [
            "| 航班 | 出发 | 到达 | 平台展示价 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in facts.rows:
        lines.append(
            "| {flight} | {depart} | {arrive} | {price} |".format(
                flight=_markdown_cell(row.flight_no),
                depart=_markdown_cell(row.depart_time),
                arrive=_markdown_cell(row.arrive_time),
                price=_format_price(row.display_price, row.currency),
            )
        )

    if facts.minimum_display_price is not None:
        minimum = _format_price(
            facts.minimum_display_price, facts.currency, code=True
        )
        lines.extend(["", f"**平台展示价最低：{minimum}。**"])

    if facts.best_deal is not None:
        best = facts.best_deal
        lines.append(
            f"推荐优先查看 {_markdown_cell(best.flight_no)}，"
            f"平台展示价 {_format_price(best.display_price, best.currency)}。"
        )

    if facts.minimum_display_price is not None and facts.budget is not None:
        budget = _format_price(facts.budget, facts.currency)
        if facts.within_budget:
            lines.append(f"当前最低平台展示价在预算 {budget} 内。")
        else:
            lines.append(
                f"当前最低平台展示价高于预算 {budget}，"
                f"可设置 {budget} 价格提醒。"
            )
    elif facts.minimum_display_price is not None:
        alert_price = _format_price(facts.minimum_display_price, facts.currency)
        lines.append(f"可设置 {alert_price} 价格提醒，继续关注价格变化。")

    if facts.has_stale_prices:
        lines.append("价格可能已更新，以预订页为准。")
    return "\n".join(lines)


def validate_optional_prose(text: str | None, facts: ResponseFacts) -> str | None:
    """Accept optional prose only when it contains no mutable fare facts."""
    del facts  # The policy rejects factual tokens even when they happen to match.
    if not isinstance(text, str) or not text.strip():
        return None
    candidate = text.strip()
    if any(
        pattern.search(candidate)
        for pattern in (
            _CURRENCY_AMOUNT_RE,
            _PRICE_OR_BUDGET_CLAIM_RE,
            _FLIGHT_NUMBER_RE,
            _TIME_RE,
        )
    ):
        return None
    return candidate
