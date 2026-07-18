import { afterEach, vi } from "vitest";
import { searchApi, type SearchStreamEvent } from "@/lib/api";

function ndjsonResponse(chunks: Uint8Array[]): Response {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(chunk));
        controller.close();
      },
    }),
    {
      status: 200,
      headers: { "content-type": "application/x-ndjson" },
    }
  );
}

function streamEvents(...events: unknown[]): Response {
  const encoder = new TextEncoder();
  return ndjsonResponse(events.map((event) => encoder.encode(`${JSON.stringify(event)}\n`)));
}

function startedEvent(overrides: Record<string, unknown> = {}) {
  return { type: "started", search_id: "search-1", sequence: 1, payload: {}, ...overrides };
}

function completeEvent(response: Record<string, unknown> = { session_id: "session-1" }) {
  return {
    type: "complete",
    search_id: "search-1",
    sequence: 5,
    payload: { response },
  };
}

function validPriceItem(overrides: Record<string, unknown> = {}) {
  return {
    id: "flyai-cny",
    name: "飞猪",
    price: 580,
    currency: "CNY",
    lowest: true,
    price_status: "priced",
    provider_status: "success",
    url: "https://example.com/book",
    data_provider: "flyai",
    data_freshness: "fresh",
    expires_at: "2099-08-01T01:00:00+00:00",
    ...overrides,
  };
}

function validDeal(overrides: Record<string, unknown> = {}) {
  return {
    id: "deal-1",
    system_id: "system-1",
    flight_no: "MU5137",
    platform: "飞猪",
    origin_city: "北京",
    origin_code: "PEK",
    destination_city: "上海",
    destination_code: "SHA",
    depart_date: "2026-08-01",
    airline: "MU",
    depart_time: "08:00",
    arrive_time: "10:30",
    duration_minutes: 150,
    stops: 0,
    price: 580,
    lowest_price: 580,
    tax: null,
    baggage_fee: null,
    has_baggage: null,
    total_price: 580,
    currency: "CNY",
    recommend_score: "8.8",
    winning_price_id: "flyai-cny",
    prices: [validPriceItem()],
    signals: ["历史低价"],
    booking_url: "https://example.com/book",
    data_freshness: "fresh",
    inventory_expires_at: "2099-08-01T01:00:00+00:00",
    ...overrides,
  };
}

function completeResponse(overrides: Record<string, unknown> = {}) {
  return {
    session_id: "session-1",
    deals: [validDeal()],
    recommendation: { text: "建议尽快预订", action: "buy_now", confidence: "high" },
    fallback: { ui: "modal", fields: ["depart_date"], reason: "需要确认日期" },
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

test("search posts to /api/search with session_id", async () => {
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(
        JSON.stringify({ deals: [], session_id: "s_x", recommendation: {} }),
        { status: 200 }
      )
    );
  await searchApi.search({ session_id: null, message: "hi" });
  const [url, init] = fetchSpy.mock.calls[0];
  expect(url).toMatch(/\/api\/search$/);
  expect(JSON.parse(init!.body as string).message).toBe("hi");
});

test("stream parses NDJSON across chunk boundaries", async () => {
  const encoder = new TextEncoder();
  const stream = ndjsonResponse([
    encoder.encode('{"type":"started","search_id":"x",'),
    encoder.encode('"sequence":1,"payload":{}}\n'),
    encoder.encode(
      '{"type":"complete","search_id":"x","sequence":2,' +
        '"payload":{"response":{"session_id":"s1","deals":[]}}}\n'
    ),
  ]);
  vi.spyOn(globalThis, "fetch").mockResolvedValue(stream);
  const events: SearchStreamEvent[] = [];

  const response = await searchApi.stream(
    { session_id: null, message: "北京到上海" },
    (event) => events.push(event)
  );

  expect(events.map((event) => event.type)).toEqual(["started", "complete"]);
  expect(response?.session_id).toBe("s1");
});

test("stream decodes a multibyte UTF-8 character split across chunks", async () => {
  const encoder = new TextEncoder();
  const line = '{"type":"validation_error","search_id":"x","sequence":1,"payload":{"message":"北京"}}\n';
  const bytes = encoder.encode(line);
  const splitAt = bytes.indexOf(0xe5) + 1;
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    ndjsonResponse([bytes.slice(0, splitAt), bytes.slice(splitAt)])
  );
  const events: SearchStreamEvent[] = [];

  await searchApi.stream({ session_id: null, message: "hi" }, (event) =>
    events.push(event)
  );

  expect(events[0].payload.message).toBe("北京");
});

test("stream accepts a final NDJSON event without a newline", async () => {
  const encoder = new TextEncoder();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    ndjsonResponse([
      encoder.encode(
        '{"type":"complete","search_id":"x","sequence":1,"payload":{"response":{"session_id":"s1","deals":[]}}}'
      ),
    ])
  );

  const response = await searchApi.stream(
    { session_id: null, message: "hi" },
    () => undefined
  );

  expect(response?.session_id).toBe("s1");
});

test("stream refreshes its session once after a 401", async () => {
  const encoder = new TextEncoder();
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ access_token: "fresh-token", user_id: "u_fresh" }), {
        status: 200,
      })
    )
    .mockResolvedValueOnce(
      ndjsonResponse([
        encoder.encode(
          '{"type":"complete","search_id":"x","sequence":1,"payload":{"response":{"session_id":"s1","deals":[]}}}\n'
        ),
      ])
    );

  await searchApi.stream({ session_id: null, message: "hi" }, () => undefined);

  expect(fetchSpy).toHaveBeenCalledTimes(3);
  expect(fetchSpy.mock.calls[1][0]).toMatch(/\/api\/session$/);
  expect((fetchSpy.mock.calls[2][1]?.headers as HeadersInit)).toMatchObject({
    authorization: "Bearer fresh-token",
  });
});

test("stream propagates AbortError while refreshing a session after a 401", async () => {
  const controller = new AbortController();
  const abortError = new DOMException("aborted", "AbortError");
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockImplementationOnce(
      (_url, init) =>
        new Promise((_, reject) => {
          (init?.signal as AbortSignal).addEventListener("abort", () => reject(abortError));
        })
    );

  const pending = searchApi.stream(
    { session_id: null, message: "hi" },
    () => undefined,
    controller.signal
  );
  await vi.waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
  controller.abort();

  await expect(pending).rejects.toBe(abortError);
  expect(fetchSpy.mock.calls[1][0]).toMatch(/\/api\/session$/);
  expect(fetchSpy.mock.calls[1][1]?.signal).toBe(controller.signal);
});

test("stream cancels and releases the reader after an abort causes read to fail", async () => {
  const controller = new AbortController();
  const abortError = new DOMException("aborted", "AbortError");
  const reader = {
    read: vi.fn(
      () =>
        new Promise<ReadableStreamReadResult<Uint8Array>>((_, reject) => {
          controller.signal.addEventListener("abort", () => reject(abortError));
        })
    ),
    cancel: vi.fn().mockResolvedValue(undefined),
    releaseLock: vi.fn(),
  };
  const response = {
    ok: true,
    status: 200,
    body: { getReader: vi.fn(() => reader) },
  } as unknown as Response;
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response);

  const pending = searchApi.stream(
    { session_id: null, message: "hi" },
    () => undefined,
    controller.signal
  );
  await vi.waitFor(() => expect(reader.read).toHaveBeenCalledTimes(1));
  controller.abort();

  await expect(pending).rejects.toBe(abortError);
  expect(reader.cancel).toHaveBeenCalledWith(abortError);
  expect(reader.releaseLock).toHaveBeenCalledTimes(1);
});

test("stream rejects malformed NDJSON instead of completing silently", async () => {
  const encoder = new TextEncoder();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    ndjsonResponse([encoder.encode("not-json\n")])
  );

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, () => undefined)
  ).rejects.toThrow();
});

test("stream rejects a JSON primitive event", async () => {
  const encoder = new TextEncoder();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    ndjsonResponse([encoder.encode("true\n")])
  );

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, () => undefined)
  ).rejects.toThrow("invalid stream event");
});

test("stream rejects when the response body is missing", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 200 }));

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, () => undefined)
  ).rejects.toThrow("stream body missing");
});

test("stream passes its AbortSignal to fetch and propagates AbortError", async () => {
  const controller = new AbortController();
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
    (_url, init) =>
      new Promise((_, reject) => {
        (init?.signal as AbortSignal).addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      })
  );

  const pending = searchApi.stream(
    { session_id: null, message: "hi" },
    () => undefined,
    controller.signal
  );
  await vi.waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
  controller.abort();

  await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  expect(fetchSpy.mock.calls[0][1]?.signal).toBe(controller.signal);
});

test("stream cancels the reader when an event callback throws", async () => {
  const encoder = new TextEncoder();
  const cancel = vi.fn();
  const response = new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('{"type":"started","search_id":"x","sequence":1,"payload":{}}\n')
        );
      },
      cancel,
    }),
    { status: 200 }
  );
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response);

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, () => {
      throw new Error("callback failed");
    })
  ).rejects.toThrow("callback failed");

  expect(cancel).toHaveBeenCalledTimes(1);
  expect(response.body?.locked).toBe(false);
});

test.each([
  ["unknown event type", startedEvent({ type: "unknown" })],
  ["missing search_id", startedEvent({ search_id: undefined })],
  ["empty search_id", startedEvent({ search_id: "" })],
  ["whitespace search_id", startedEvent({ search_id: "   " })],
  ["non-positive sequence", startedEvent({ sequence: 0 })],
  ["non-integer sequence", startedEvent({ sequence: 1.5 })],
  ["non-object payload", startedEvent({ payload: [] })],
])("stream rejects %s before invoking onEvent", async (_description, event) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(streamEvents(event));
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test("stream rejects malformed results deals before invoking onEvent", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents({
      type: "results",
      search_id: "search-1",
      sequence: 2,
      payload: { deals: [null] },
    })
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test.each([
  [
    "provider_status without a string provider",
    { type: "provider_status", search_id: "search-1", sequence: 2, payload: { provider: 1, status: "loading" } },
  ],
  [
    "provider_status with an unknown status",
    { type: "provider_status", search_id: "search-1", sequence: 2, payload: { provider: "flyai", status: "unknown" } },
  ],
  [
    "results without a deals array",
    { type: "results", search_id: "search-1", sequence: 2, payload: { deals: {} } },
  ],
  [
    "validation_error without a string message",
    { type: "validation_error", search_id: "search-1", sequence: 2, payload: { message: 1 } },
  ],
])("stream rejects %s before invoking onEvent", async (_description, event) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(streamEvents(event));
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test("stream accepts valid lifecycle events and a canonical complete response", async () => {
  const events = [
    startedEvent(),
    {
      type: "provider_status",
      search_id: "search-1",
      sequence: 2,
      payload: { provider: "flyai", status: "loading" },
    },
    { type: "results", search_id: "search-1", sequence: 3, payload: { deals: [] } },
    {
      type: "validation_error",
      search_id: "search-1",
      sequence: 4,
      payload: { message: "请输入出发日期" },
    },
    completeEvent({
      session_id: "session-1",
      deals: [],
      recommendation: { text: "建议尽快预订" },
      fallback: null,
    }),
  ];
  vi.spyOn(globalThis, "fetch").mockResolvedValue(streamEvents(...events));
  const onEvent = vi.fn();

  const response = await searchApi.stream({ session_id: null, message: "hi" }, onEvent);

  expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual(
    events.map((event) => event.type)
  );
  expect(response).toMatchObject({ session_id: "session-1", deals: [] });
});

test.each([
  ["a string response", { response: "not-a-response" }],
  ["an array response", { response: [] }],
  ["a response without session_id", { response: {} }],
  ["a response with non-string session_id", { response: { session_id: 1 } }],
  ["a response with non-array deals", { response: { session_id: "s1", deals: {} } }],
  ["a response with non-object recommendation", { response: { session_id: "s1", recommendation: [] } }],
  ["a response with invalid fallback", { response: { session_id: "s1", fallback: 1 } }],
  ["a failure response mixed with a canonical response", { response: { session_id: "s1" }, error: "search_failed", message: "暂时不可用" }],
  ["a failure response with non-string error", { error: 1, message: "暂时不可用" }],
  ["a failure response with non-string message", { error: "search_failed", message: 1 }],
])("stream rejects complete with %s before invoking onEvent", async (_description, payload) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents({
      type: "complete",
      search_id: "search-1",
      sequence: 5,
      payload,
    })
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test("stream accepts a canonical sanitized failure complete payload", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents({
      type: "complete",
      search_id: "search-1",
      sequence: 5,
      payload: { error: "search_failed", message: "搜索暂时不可用，请稍后重试" },
    })
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).resolves.toBeNull();

  expect(onEvent).toHaveBeenCalledTimes(1);
});

test.each([
  ["a duplicate complete", [completeEvent({ session_id: "first" }), completeEvent({ session_id: "second" })]],
  [
    "an event after complete",
    [
      completeEvent({ session_id: "first" }),
      { type: "results", search_id: "search-1", sequence: 6, payload: { deals: [] } },
    ],
  ],
])("stream rejects %s without invoking onEvent for the rejected event", async (_description, events) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(streamEvents(...events));
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("stream event received after complete");

  expect(onEvent).toHaveBeenCalledTimes(1);
  expect(onEvent.mock.calls[0][0].payload.response.session_id).toBe("first");
});

test.each([
  ["an empty recommendation", { recommendation: {} }],
  ["a recommendation with non-string text", { recommendation: { text: 1 } }],
  ["a recommendation with non-string action", { recommendation: { text: "预订", action: 1 } }],
  ["a recommendation with non-string confidence", { recommendation: { text: "预订", confidence: 1 } }],
  ["an empty fallback", { fallback: {} }],
  ["a fallback with the wrong ui", { fallback: { ui: "banner", fields: [], reason: "x" } }],
  ["a fallback with non-string fields", { fallback: { ui: "modal", fields: [1], reason: "x" } }],
  ["a fallback with non-string reason", { fallback: { ui: "modal", fields: [], reason: 1 } }],
])("stream rejects complete with %s before invoking onEvent", async (_description, overrides) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents(completeEvent(completeResponse(overrides)))
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test.each([
  ["a null deal", [null]],
  ["a deal missing id", [validDeal({ id: undefined })]],
  ["a deal missing winning_price_id", [validDeal({ winning_price_id: undefined })]],
  ["a deal with non-string required fields", [validDeal({ origin_city: 1 })]],
  ["a deal with non-array prices", [validDeal({ prices: {} })]],
  ["a deal with non-string signals", [validDeal({ signals: [1] })]],
  ["a deal with non-nullable money type", [validDeal({ tax: "50" })]],
  ["a deal with an invalid baggage flag", [validDeal({ has_baggage: 0 })]],
  ["a price item with non-string name", [validDeal({ prices: [validPriceItem({ name: 1 })] })]],
  ["a price item with invalid price", [validDeal({ prices: [validPriceItem({ price: "580" })] })]],
  ["a price item with invalid price status", [validDeal({ prices: [validPriceItem({ price_status: "unknown" })] })]],
  ["a price item with invalid provider status", [validDeal({ prices: [validPriceItem({ provider_status: "priced" })] })]],
  ["a price item with invalid currency", [validDeal({ prices: [validPriceItem({ currency: "usd" })] })]],
  ["a price item with invalid lowest", [validDeal({ prices: [validPriceItem({ lowest: "true" })] })]],
  ["a price item with invalid url", [validDeal({ prices: [validPriceItem({ url: 1 })] })]],
  ["a price item with invalid data provider", [validDeal({ prices: [validPriceItem({ data_provider: 1 })] })]],
  ["a price item missing data freshness", [validDeal({ prices: [validPriceItem({ data_freshness: undefined })] })]],
  ["a price item with invalid data freshness", [validDeal({ prices: [validPriceItem({ data_freshness: "recent" })] })]],
  ["a price item with invalid expiry", [validDeal({ prices: [validPriceItem({ expires_at: "eventually" })] })]],
  ["a winner id that is absent from prices", [validDeal({ winning_price_id: "missing-row" })]],
  ["a nonwinner also marked lowest", [validDeal({ prices: [validPriceItem(), validPriceItem({ id: "other-row", name: "其他", price: 600, lowest: true, url: null })] })]],
  ["a nonwinner with null lowest", [validDeal({ prices: [validPriceItem(), validPriceItem({ id: "other-row", name: "其他", price: 600, lowest: null, url: null })] })]],
  ["a no-winner row with null lowest", [validDeal({ platform: "", price: null, lowest_price: null, total_price: null, winning_price_id: null, booking_url: null, data_freshness: "unknown", inventory_expires_at: null, prices: [validPriceItem({ lowest: null, price_status: "stale", provider_status: "stale", url: null, data_freshness: "unknown", expires_at: null })] })]],
  ["a winner URL without a card booking URL", [validDeal({ booking_url: undefined })]],
  ["a booking fallback that disagrees with the winner", [validDeal({ h5_fallback_url: "https://other.example.com/book" })]],
  ["a deal with invalid data freshness", [validDeal({ data_freshness: "recent" })]],
  ["a deal with invalid optional fields", [validDeal({ original_price: "650", discount_rate: "0.1", cabin: 1, booking_url: 1, data_freshness: 1 })]],
])("stream rejects complete with %s before invoking onEvent", async (_description, deals) => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents(completeEvent(completeResponse({ deals })))
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test("stream rejects a deal with non-finite nullable money", async () => {
  const rawEvent = JSON.stringify(completeEvent(completeResponse())).replace(
    '"price":580',
    '"price":1e400'
  );
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    ndjsonResponse([new TextEncoder().encode(`${rawEvent}\n`)])
  );
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).rejects.toThrow("invalid stream event");

  expect(onEvent).not.toHaveBeenCalled();
});

test("stream accepts a complete response with fully validated nested DTOs", async () => {
  const response = completeResponse();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(streamEvents(completeEvent(response)));
  const onEvent = vi.fn();

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, onEvent)
  ).resolves.toEqual(response);

  expect(onEvent).toHaveBeenCalledTimes(1);
});

test("stream accepts an explicit false lowest state for a nonwinner", async () => {
  const response = completeResponse({
    deals: [
      validDeal({
        prices: [
          validPriceItem(),
          validPriceItem({
            id: "ctrip-status-cny",
            name: "携程",
            price: null,
            lowest: false,
            price_status: null,
            provider_status: "queued",
            url: null,
            data_provider: "ctrip_snapshot",
            data_freshness: "unknown",
          }),
        ],
      }),
    ],
  });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    streamEvents(completeEvent(response))
  );

  await expect(
    searchApi.stream({ session_id: null, message: "hi" }, () => undefined)
  ).resolves.toEqual(response);
});
