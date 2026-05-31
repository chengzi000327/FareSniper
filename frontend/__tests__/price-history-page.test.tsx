import React from "react";
import { vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PriceHistoryPage from "@/app/price-history/[route]/page";

vi.mock("@/lib/api", () => ({ priceHistoryApi: {
  get: vi.fn().mockResolvedValue({ route: "BJS-SYX", points: [
    { at: "2026-04-01T00:00:00Z", price: 520 }, { at: "2026-04-15T00:00:00Z", price: 480 }
  ]})
}}));

test("renders chart with points", async () => {
  render(<PriceHistoryPage params={Promise.resolve({ route: "BJS-SYX" })} />);
  await waitFor(() => expect(screen.getByTestId("price-chart")).toBeInTheDocument());
});
