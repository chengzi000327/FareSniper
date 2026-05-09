import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ChatPage } from "@/components/chat-page";
import { searchApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  searchApi: {
    search: vi.fn()
      .mockResolvedValueOnce({
        session_id: "s_first",
        deals: [],
        recommendation: { text: "你想去哪里？" },
      })
      .mockResolvedValueOnce({
        session_id: "s_first",
        deals: [],
        recommendation: { text: "哪天出发？" },
      }),
  },
  recApi: {
    list: vi.fn().mockResolvedValue({
      personalized: false,
      cards: [{ query_hint: "北京去上海" }],
    }),
  },
}));

test("chat page reuses backend session id across turns", async () => {
  render(<ChatPage />);

  fireEvent.change(screen.getByRole("textbox"), { target: { value: "从北京出发" } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

  await waitFor(() => expect(searchApi.search).toHaveBeenCalledTimes(1));
  expect(searchApi.search).toHaveBeenNthCalledWith(1, {
    message: "从北京出发",
    session_id: null,
  });

  fireEvent.change(screen.getByRole("textbox"), { target: { value: "去上海" } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

  await waitFor(() => expect(searchApi.search).toHaveBeenCalledTimes(2));
  expect(searchApi.search).toHaveBeenNthCalledWith(2, {
    message: "去上海",
    session_id: "s_first",
  });
});
