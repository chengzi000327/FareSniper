import { vi } from "vitest";
import { searchApi } from "@/lib/api";

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
