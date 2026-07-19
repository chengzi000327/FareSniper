import React from "react";
import { beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExplorePage } from "@/components/explore-page";

const { listMock } = vi.hoisted(() => ({ listMock: vi.fn() }));

vi.mock("@/lib/api", () => ({
  recApi: { list: listMock },
}));

function recommendationCard() {
  return {
    id: "rec-sin",
    title: "上海→新加坡",
    query_hint: "2099-08-01 从上海到新加坡的机票",
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
      base_price: 80,
      lowest_price: 80,
      tax: null,
      baggage_fee: null,
      has_baggage: null,
      total_price: 80,
      currency: "USD",
      recommend_score: null,
      winning_price_id: "serpapi-global-usd",
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
          data_freshness: "fresh",
        },
      ],
      signals: [],
      data_freshness: "fresh",
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

test("hands a recommendation query to the chat callback", async () => {
  listMock.mockResolvedValue({
    personalized: false,
    cards: [recommendationCard()],
    has_more: false,
    next_offset: 1,
  });
  const onSearch = vi.fn();

  render(<ExplorePage onSearch={onSearch} />);

  fireEvent.click(await screen.findByRole("button", { name: "查看详情" }));
  fireEvent.click(await screen.findByRole("button", { name: "在对话中查询" }));

  expect(onSearch).toHaveBeenCalledWith("2099-08-01 从上海到新加坡的机票");
});

test("renders an unpriced route and hands it to realtime chat search", async () => {
  listMock.mockResolvedValue({
    personalized: false,
    cards: [
      {
        id: "route-syx",
        title: "北京→三亚",
        query_hint: "明天从北京到三亚的机票",
        reason: "进入对话获取最新报价",
        tags: ["海岛度假"],
        preview_deal: null,
      },
    ],
    has_more: false,
    next_offset: 1,
  });
  const onSearch = vi.fn();

  render(<ExplorePage onSearch={onSearch} />);

  expect(await screen.findByText("实时查询")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "查询实时价格" }));
  fireEvent.click(await screen.findByRole("button", { name: "在对话中查询" }));

  expect(onSearch).toHaveBeenCalledWith("明天从北京到三亚的机票");
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

test("loads the next recommendation page after the first six-card page", async () => {
  listMock
    .mockResolvedValueOnce({
      personalized: false,
      cards: [recommendationCard()],
      has_more: true,
      next_offset: 6,
    })
    .mockResolvedValueOnce({
      personalized: false,
      cards: [
        {
          id: "route-syx-next-page",
          title: "北京→三亚",
          query_hint: "明天从北京到三亚的机票",
          reason: "进入对话获取最新报价",
          tags: ["海岛度假"],
          preview_deal: null,
        },
      ],
      has_more: false,
      next_offset: 7,
    });

  render(<ExplorePage />);

  fireEvent.click(await screen.findByRole("button", { name: "加载更多目的地" }));

  await waitFor(() =>
    expect(listMock).toHaveBeenLastCalledWith({ limit: 6, offset: 6 })
  );
  expect(await screen.findByText("北京 → 三亚")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "加载更多目的地" })).not.toBeInTheDocument();
});
