import React from "react";
import { vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PersonalPage from "@/app/personal/page";
import { PersonalPage as ConnectedPersonalPage } from "@/components/personal-page";

vi.mock("@/lib/api", () => ({
  alertsApi: { list: vi.fn().mockResolvedValue({ alerts: [
    { id: "a1", origin: "BJS", destination: "SYX", depart_date: "2026-05-01", target_price: 500, status: "active" }
  ]})},
  memoryApi: { get: vi.fn().mockResolvedValue({
    memories: [{ field: "budget", value: 600, label: "心理价位", value_display: "¥600", source: "manual" }],
    query_history: [{ id: "q1", query: { text: "北京去三亚" }, created_at: "2026-07-23T00:00:00Z" }],
  })},
}));

test("renders alerts list", async () => {
  render(<PersonalPage />);
  await waitFor(() => expect(screen.getByText(/BJS.*SYX/)).toBeInTheDocument());
});

test("the main web personal center reads real alerts and memory", async () => {
  render(<ConnectedPersonalPage />);
  expect((await screen.findAllByText("BJS → SYX")).length).toBeGreaterThan(0);
  expect(screen.getByText("北京去三亚")).toBeInTheDocument();
  expect(screen.getByText("1 条监控中 · 1 条已保存")).toBeInTheDocument();
  expect(screen.getByText("1 次查询 · 1 项记忆")).toBeInTheDocument();
  expect(screen.queryByText(/me@faresniper/)).not.toBeInTheDocument();
});
