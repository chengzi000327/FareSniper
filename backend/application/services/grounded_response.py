"""Build deterministic response text from a frozen final deal snapshot."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence


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


def _winning_price_row(deal: Mapping[str, Any]) -> Mapping[str, Any] | None:
    winning_price_id = deal.get("winning_price_id")
    if not isinstance(winning_price_id, str) or not winning_price_id.strip():
        return None
    matches = [
        item
        for item in deal.get("prices") or ()
        if isinstance(item, Mapping) and item.get("id") == winning_price_id
    ]
    if len(matches) != 1:
        raise ValueError("winning price id must resolve to exactly one row")
    return matches[0]


def _display_price(
    deal: Mapping[str, Any], default_currency: str
) -> tuple[int | None, str, Mapping[str, Any] | None]:
    deal_currency = _currency(deal.get("currency")) or default_currency
    winner = _winning_price_row(deal)
    if winner is None:
        for key in ("display_price", "price", "total_price", "lowest_price"):
            price = _numeric_price(deal.get(key))
            if price is not None:
                return price, deal_currency, None
        return None, deal_currency, None

    if winner.get("provider_status") in _INELIGIBLE_PROVIDER_STATUSES:
        raise ValueError("winning price row is not eligible")
    price = _numeric_price(winner.get("price"))
    winner_currency = _currency(winner.get("currency"))
    if price is None or winner_currency is None:
        raise ValueError("winning price row must have a valid amount and currency")
    if _currency(deal.get("currency")) not in (None, winner_currency):
        raise ValueError("winning price currency must match the card headline")
    for key in ("display_price", "price", "total_price", "lowest_price"):
        headline_price = _numeric_price(deal.get(key))
        if headline_price is not None and headline_price != price:
            raise ValueError("winning price must match the card headline")
    return price, winner_currency, winner


def _has_stale_price(
    deal: Mapping[str, Any], winner: Mapping[str, Any] | None
) -> bool:
    selected = winner if winner is not None else deal
    return any(
        selected.get(key) == "stale"
        for key in ("data_freshness", "price_status", "provider_status")
    )


@dataclass(frozen=True, slots=True)
class ResponseRow:
    flight_no: str
    platform: str
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
    response_rows: list[ResponseRow] = []
    for deal in snapshot:
        display_price, display_currency, winner = _display_price(deal, currency)
        response_rows.append(
            ResponseRow(
                flight_no=str(deal.get("flight_no") or "待确认"),
                platform=str(
                    (winner or {}).get("name")
                    or deal.get("platform")
                    or "待确认"
                ),
                depart_time=str(deal.get("depart_time") or "待确认"),
                arrive_time=str(deal.get("arrive_time") or "待确认"),
                display_price=display_price,
                currency=display_currency,
                is_stale=_has_stale_price(deal, winner),
                card=_freeze(deal),
            )
        )
    rows = tuple(response_rows)
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
            "| 航班 | 平台 | 出发 | 到达 | 平台展示价 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in facts.rows:
        lines.append(
            "| {flight} | {platform} | {depart} | {arrive} | {price} |".format(
                flight=_markdown_cell(row.flight_no),
                platform=_markdown_cell(row.platform),
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
            f"在 {_markdown_cell(best.platform)} 的平台展示价为 "
            f"{_format_price(best.display_price, best.currency)}。"
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
    """Conservatively reject model prose when final deals are available."""
    del text, facts
    return None
