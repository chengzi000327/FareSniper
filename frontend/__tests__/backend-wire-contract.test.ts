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
  ]);
  expect(deal?.prices.map((row) => row.currency)).toEqual(["CNY", "USD"]);
  expect(deal?.booking_url).toContain(
    "?offer=fixture-token-not-secret&channel=web"
  );
  expect(response?.session_id).toBe("fixture-session");
});
