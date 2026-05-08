import React from "react";
import { vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PersonalPage from "@/app/personal/page";

vi.mock("@/lib/api", () => ({
  alertsApi: { list: vi.fn().mockResolvedValue({ alerts: [
    { id: "a1", origin: "BJS", destination: "SYX", depart_date: "2026-05-01", target_price: 500, status: "active" }
  ]})}
}));

test("renders alerts list", async () => {
  render(<PersonalPage />);
  await waitFor(() => expect(screen.getByText(/BJS.*SYX/)).toBeInTheDocument());
});
