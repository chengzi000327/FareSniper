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
