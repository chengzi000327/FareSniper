import React from "react";
import { vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import MemoryPage from "@/app/memory/page";

vi.mock("@/lib/api", () => ({
  memoryApi: { get: vi.fn().mockResolvedValue({
    memories: [{ field: "budget_ceiling", value: 500, source: "user" }],
    query_history: []
  })}
}));

test("renders memory items", async () => {
  render(<MemoryPage />);
  await waitFor(() => expect(screen.getByText(/budget_ceiling/)).toBeInTheDocument());
});
