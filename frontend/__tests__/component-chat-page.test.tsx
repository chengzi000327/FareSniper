import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { vi } from "vitest";
import { ChatPage } from "@/components/chat-page";
import { searchApi } from "@/lib/api";

let resolveStream: (() => void) | undefined;

vi.mock("@/lib/api", () => ({
  searchApi: {
    search: vi.fn(),
    stream: vi.fn((_body, onEvent) =>
      new Promise((resolve) => {
        onEvent({
          type: "started",
          search_id: "search_first",
          sequence: 1,
          payload: {},
        });
        onEvent({
          type: "results",
          search_id: "search_first",
          sequence: 2,
          payload: {
            deals: [
              {
                id: "deal_1",
                system_id: "sys_1",
                platform: "飞猪",
                origin_city: "北京",
                origin_code: "BJS",
                destination_city: "上海",
                destination_code: "SHA",
                depart_date: "2026-08-01",
                airline: "CA",
                depart_time: "08:00",
                arrive_time: "10:00",
                price: 580,
                tax: null,
                baggage_fee: null,
                has_baggage: null,
                total_price: null,
                currency: "CNY",
                recommend_score: "9.5",
                prices: [
                  { name: "飞猪", price: 580, status: "success", lowest: true },
                  { name: "携程", price: null, status: "loading", data_provider: "ctrip_snapshot" },
                ],
                signals: [],
              },
            ],
          },
        });
        resolveStream = () => {
          onEvent({
            type: "complete",
            search_id: "search_first",
            sequence: 3,
            payload: {
              response: {
                session_id: "s_first",
                deals: [
                  {
                    id: "deal_1",
                    system_id: "sys_1",
                    platform: "飞猪",
                    origin_city: "北京",
                    origin_code: "BJS",
                    destination_city: "上海",
                    destination_code: "SHA",
                    depart_date: "2026-08-01",
                    airline: "CA",
                    depart_time: "08:00",
                    arrive_time: "10:00",
                    price: 580,
                    tax: null,
                    baggage_fee: null,
                    has_baggage: null,
                    total_price: null,
                    currency: "CNY",
                    recommend_score: "9.5",
                    prices: [
                      { name: "飞猪", price: 580, status: "success", lowest: true },
                      { name: "携程", price: null, status: "queued", data_provider: "ctrip_snapshot" },
                    ],
                    signals: [],
                  },
                ],
                recommendation: { text: "飞猪当前价格更优" },
              },
            },
          });
          resolve({
            session_id: "s_first",
            deals: [],
            recommendation: { text: "飞猪当前价格更优" },
          });
        };
      })
    ),
  },
  recApi: {
    list: vi.fn().mockResolvedValue({
      personalized: false,
      cards: [{ query_hint: "北京去上海" }],
    }),
  },
}));

test("chat page updates its card when results arrive before the stream completes", async () => {
  render(<ChatPage />);

  fireEvent.change(screen.getByRole("textbox"), { target: { value: "从北京出发" } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

  await waitFor(() => expect(searchApi.stream).toHaveBeenCalledTimes(1));
  expect(searchApi.stream).toHaveBeenNthCalledWith(1, {
    message: "从北京出发",
    session_id: null,
  }, expect.any(Function), expect.any(AbortSignal));

  expect((await screen.findAllByText("飞猪")).length).toBeGreaterThan(0);
  expect(screen.getByText("正在获取数据")).toBeInTheDocument();
  expect(screen.queryByText("飞猪当前价格更优")).not.toBeInTheDocument();

  await act(async () => {
    resolveStream?.();
  });

  expect(await screen.findByText("飞猪当前价格更优")).toBeInTheDocument();
  expect(screen.getByText("等待下次刷新")).toBeInTheDocument();
});
