import { vi } from "vitest";
import { track, EventName } from "@/lib/analytics";

test("track posts to /api/track and includes event name", async () => {
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await track(EventName.SearchSubmitted, { user_id: "u1", query_text: "hi", clarify_count: 0 });
  const [url, init] = spy.mock.calls[0];
  expect(url).toMatch(/\/api\/track$/);
  expect(JSON.parse(init!.body as string).event).toBe("search_submitted");
});
