import React from "react";
import { vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ExplorePage from "@/app/explore/page";

vi.mock("@/lib/api", () => ({
  recApi: { list: vi.fn().mockResolvedValue({ personalized: false, cards: [
    { title: "BJS-SYX", reason: "热门航线", preview_deal: { price: 480, platform: "ctrip" } }
  ]}) }
}));

test("renders cards from recApi", async () => {
  render(<ExplorePage />);
  await waitFor(() => expect(screen.getByText("BJS-SYX")).toBeInTheDocument());
});
