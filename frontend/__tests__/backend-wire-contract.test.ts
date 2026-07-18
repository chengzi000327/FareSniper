import { afterEach, vi } from "vitest";
import { searchApi, type SearchStreamEvent } from "@/lib/api";
import fixture from "./fixtures/backend-progressive-search.ndjson?raw";

afterEach(() => {
  vi.restoreAllMocks();
});

test("parses the committed backend progressive payload without contract drift", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(fixture, {
      status: 200,
      headers: { "content-type": "application/x-ndjson" },
    })
  );
  const events: SearchStreamEvent[] = [];

  const response = await searchApi.stream(
    { session_id: null, message: "北京到上海" },
    (event) => events.push(event)
  );

  expect(events.map((event) => event.type)).toEqual([
    "started",
    "provider_status",
    "results",
    "complete",
  ]);
  const deal = events[2].payload.deals?.[0];
  expect(deal?.recommend_score).toBeNull();
  expect(deal?.prices.map((row) => row.price_status)).toEqual([
    "priced",
    "priced",
    "priced",
  ]);
  expect(deal?.prices.map((row) => row.currency)).toEqual([
    "CNY",
    "CNY",
    "USD",
  ]);
  const winner = deal?.prices.find((row) => row.id === deal.winning_price_id);
  const snapshot = deal?.prices.find(
    (row) => row.data_provider === "ctrip_snapshot"
  );
  expect(winner).toMatchObject({
    name: "携程",
    price: 500,
    lowest: true,
    data_freshness: "fresh",
  });
  expect(snapshot).toMatchObject({
    name: "携程",
    price: 500,
    lowest: true,
  });
  expect(deal?.platform).toBe(winner?.name);
  expect(deal?.total_price).toBe(winner?.price);
  expect(deal?.booking_url).toBe(winner?.url);
  expect(deal?.data_freshness).toBe("fresh");
  expect(deal?.inventory_expires_at).toBe(winner?.expires_at);
  expect(
    deal?.prices
      .filter((row) => row.id !== deal.winning_price_id)
      .every((row) => row.lowest === false)
  ).toBe(true);
  expect(deal?.booking_url).toBe("https://ctrip.example.test/reference");
  expect(deal?.prices.some((row) =>
    row.url?.endsWith("?offer=fixture-token-not-secret&channel=web")
  )).toBe(true);
  expect(response?.session_id).toBe("fixture-session");
});
