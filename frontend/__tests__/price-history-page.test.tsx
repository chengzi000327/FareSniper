import React from "react";
import { vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import PriceHistoryPage from "@/app/price-history/[route]/page";

vi.mock("@/lib/api", () => ({ priceHistoryApi: {
  get: vi.fn().mockResolvedValue({ route: "BJS-SYX", points: [
    { at: "2026-04-01T00:00:00Z", price: 520 }, { at: "2026-04-15T00:00:00Z", price: 480 }
  ]})
}}));

test("renders chart with points", async () => {
  await act(async () => {
    render(
      <React.Suspense fallback={null}>
        <PriceHistoryPage params={Promise.resolve({ route: "BJS-SYX" })} />
      </React.Suspense>,
    );
  });

  expect(await screen.findByTestId("price-chart")).toBeInTheDocument();
});
