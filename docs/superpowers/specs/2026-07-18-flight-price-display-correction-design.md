# Flight Price Display Correction Design

**Date:** 2026-07-18

## Goal

Restore numeric prices in production flight cards. FlyAI live offers must use the price field returned by the current CLI, and the latest stored Ctrip snapshot must remain visible and eligible to win the price comparison even after its freshness window expires.

## Confirmed Product Rules

- FlyAI flight results use the current production `ticketPrice` value. The legacy `adultPrice` field remains supported as a compatibility fallback.
- A Ctrip snapshot with a numeric price remains visible after expiry.
- The UI displays only the Ctrip amount, without "上次采集" or "价格可能已更新" replacing the number.
- Expired Ctrip prices participate in the same-currency minimum-price comparison.
- If an expired Ctrip price wins, it drives the card headline price, the "最低" badge, and the Ctrip booking link.
- The existing worker still refreshes Ctrip inventory hourly. Reading an expired snapshot continues to enqueue a refresh demand.
- No fabricated price, tax, fuel surcharge, or baggage fee is introduced. Unknown components remain "待确认" while the known total price is displayed.

## Root Cause

The deployed FlyAI CLI currently returns a top-level `ticketPrice`, while `FlyAIProvider` only parses `adultPrice`. The offer therefore retains its flight details and `jumpUrl` but loses its numeric price.

Ctrip snapshot offers already retain their numeric price. However, the normalizer excludes stale offers from winner selection, and the frontend replaces stale numeric rows with freshness copy. Together these rules hide the last collected amount and prevent it from driving the card.

## Data Flow

### FlyAI

`parse_flyai_payload` reads the first usable value from:

1. `ticketPrice`
2. `adultPrice`

The existing decimal parser converts the value to an integer amount. Invalid, negative, or non-finite values remain unpriced. A valid HTTPS `jumpUrl` is preserved.

### Ctrip Snapshot

`CtripSnapshotProvider` continues to mark expired inventory as stale and enqueue a refresh. The stale marker remains available as metadata, but numeric stale offers are eligible for winner selection when they have a valid amount, currency, and booking URL.

Winner selection compares numeric offers in the preferred currency. A lower Ctrip snapshot may beat a higher FlyAI live offer. The selected winner supplies:

- headline price and total price;
- platform name;
- booking URL;
- winning row identifier and "最低" badge.

The winner contract must explicitly accept a priced Ctrip snapshot even when its freshness metadata is stale. It must not relabel the stale row as fresh or real-time.

### Frontend

For any row containing a numeric price, the row renders the formatted amount. Provider status text is used only when no numeric amount exists. This prevents stale status copy from replacing a known Ctrip amount.

The card accepts the backend-selected winner. A stale Ctrip winner can show the minimum badge and enable its HTTPS booking link. Real-time marketing copy remains reserved for a fresh winner; a stale winner is presented as a price comparison rather than "实时底价" or "全网多端实时同步".

## Error Handling

- Missing FlyAI prices still fall back to `view_live_price` only when a valid HTTPS jump URL exists.
- Invalid FlyAI price fields never become zero or fabricated values.
- A stale Ctrip row without a numeric price cannot win.
- A missing or invalid HTTPS booking URL cannot enable the booking action.
- Ctrip refresh demand behavior remains unchanged, so stale data is displayed while a replacement collection is requested.

## Tests

- FlyAI parser regression fixture using production-shaped `ticketPrice`.
- Compatibility test proving `adultPrice` still works when `ticketPrice` is absent.
- Precedence test proving a valid `ticketPrice` wins over `adultPrice`.
- Normalizer test where stale Ctrip `500 CNY` beats live FlyAI `560 CNY` and drives the headline and booking URL.
- Schema/wire contract test accepting a stale priced winner without claiming freshness.
- Frontend test rendering the stale Ctrip amount, minimum badge, and booking link while omitting stale replacement copy and real-time marketing copy.
- Existing FlyAI, normalizer, API contract, and card suites remain green.

## Non-Goals

- Changing the hourly Ctrip worker schedule.
- Treating a stale Ctrip snapshot as fresh inventory.
- Adding a timestamp or stale-data label to the visible card.
- Inventing tax, fuel, or baggage amounts that providers did not return.
