import React from "react";
import { vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChatPage from "@/app/chat/page";

const mockSend = vi.fn().mockResolvedValue({ deals: [], recommendation: null, session_id: "s_1" });

vi.mock("@/lib/useChatSession", () => ({
  useChatSession: () => ({
    sessionId: null,
    messages: [],
    fallback: null,
    send: mockSend,
    dismissFallback: vi.fn(),
  }),
}));

beforeEach(() => {
  mockSend.mockClear();
});

test("submitting message calls send from useChatSession", async () => {
  render(<ChatPage />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "明天去三亚" } });
  fireEvent.click(screen.getByRole("button", { name: /发送/ }));
  await waitFor(() => expect(mockSend).toHaveBeenCalledTimes(1));
  expect(mockSend).toHaveBeenCalledWith("明天去三亚");
});
