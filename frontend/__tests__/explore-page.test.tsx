import React from "react";
import { beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ExplorePage } from "@/components/explore-page";

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }));

vi.mock("@/lib/api", () => ({
  recApi: { list: listMock },
}));

function recommendationCard() {
  return {
    id: "rec-sin",
    title: "上海→新加坡",
    reason: "未来航班",
    tags: [],
    preview_deal: {
      id: "deal-sin",
      system_id: "SQ833-2099-08-01",
      flight_no: "SQ833",
      platform: "Global Seller",
      origin_city: "上海",
      origin_code: "SHA",
      destination_city: "新加坡",
      destination_code: "SIN",
      depart_date: "2099-08-01",
      airline: "Singapore Airlines",
      depart_time: "08:00",
      arrive_time: "14:00",
      duration_minutes: 360,
      stops: 0,
      price: 80,
      lowest_price: 80,
      tax: null,
      baggage_fee: null,
      has_baggage: null,
      total_price: 80,
      currency: "USD",
      recommend_score: null,
      prices: [
        {
          id: "serpapi-global-usd",
          name: "Global Seller",
          price: 80,
          currency: "USD",
          lowest: true,
          price_status: "priced",
          provider_status: "success",
          data_provider: "serpapi_google_flights",
        },
      ],
      signals: [],
    },
  };
}

beforeEach(() => {
  listMock.mockReset();
});

test("renders cards from recApi", async () => {
  listMock.mockResolvedValue({
    personalized: false,
    cards: [recommendationCard()],
    has_more: false,
    next_offset: 1,
  });

  render(<ExplorePage />);

  await waitFor(() => expect(screen.getByText("上海 → 新加坡")).toBeInTheDocument());
});

test("continues past an empty first page and renders a later valid page", async () => {
  listMock
    .mockResolvedValueOnce({
      personalized: false,
      cards: [{ id: "empty", title: "empty", reason: "empty", preview_deal: null }],
      has_more: true,
      next_offset: 1,
    })
    .mockResolvedValueOnce({
      personalized: false,
      cards: [recommendationCard()],
      has_more: false,
      next_offset: 2,
    });

  render(<ExplorePage />);

  await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  expect(await screen.findByText("上海 → 新加坡")).toBeInTheDocument();
  expect(
    screen.getByText(
      new Intl.NumberFormat("zh-CN", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(80)
    )
  ).toBeInTheDocument();
});
