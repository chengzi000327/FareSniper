import { renderHook, act } from "@testing-library/react";
import { vi } from "vitest";
import { useChatSession } from "@/lib/useChatSession";

vi.mock("@/lib/api", () => ({
  searchApi: {
    search: vi.fn().mockResolvedValue({
      session_id: "s_abc123",
      recommendation: { text: "推荐购买" },
      fallback: null,
    }),
  },
}));

test("first send stores session_id", async () => {
  const { result } = renderHook(() => useChatSession());
  await act(async () => {
    await result.current.send("明天去三亚");
  });
  expect(result.current.sessionId).toBe("s_abc123");
});

test("messages are appended after send", async () => {
  const { result } = renderHook(() => useChatSession());
  await act(async () => {
    await result.current.send("明天去三亚");
  });
  expect(result.current.messages).toHaveLength(2);
  expect(result.current.messages[0]).toMatchObject({ role: "user", content: "明天去三亚" });
  expect(result.current.messages[1]).toMatchObject({ role: "assistant" });
});

test("fallback directive is exposed when present", async () => {
  const { searchApi } = await import("@/lib/api");
  (searchApi.search as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    session_id: "s_abc123",
    recommendation: { text: "" },
    fallback: { ui: "modal", fields: ["origin"], reason: "缺少出发地" },
  });
  const { result } = renderHook(() => useChatSession());
  await act(async () => {
    await result.current.send("想去三亚");
  });
  expect(result.current.fallback).toMatchObject({ ui: "modal" });
});

test("dismissFallback clears fallback state", async () => {
  const { searchApi } = await import("@/lib/api");
  (searchApi.search as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    session_id: "s_abc123",
    recommendation: { text: "" },
    fallback: { ui: "modal", fields: ["origin"], reason: "缺少出发地" },
  });
  const { result } = renderHook(() => useChatSession());
  await act(async () => {
    await result.current.send("想去三亚");
  });
  act(() => { result.current.dismissFallback(); });
  expect(result.current.fallback).toBeNull();
});
