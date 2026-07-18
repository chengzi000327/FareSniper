import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { ChatPage } from "@/components/chat-page";
import { searchApi } from "@/lib/api";
import type { ChatSearchResponse, DealCardDto, PriceItem, SearchStreamEvent } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  searchApi: {
    search: vi.fn(),
    stream: vi.fn(),
  },
  recApi: {
    list: vi.fn().mockResolvedValue({
      personalized: false,
      cards: [{ query_hint: "北京去上海" }],
    }),
  },
}));

type StreamCall = {
  onEvent: (event: SearchStreamEvent) => void;
  signal: AbortSignal | undefined;
  resolve: (response: ChatSearchResponse | null) => void;
  reject: (error: Error) => void;
};

const calls: StreamCall[] = [];
const streamMock = vi.mocked(searchApi.stream);

function priceRow(overrides: Partial<PriceItem> = {}): PriceItem {
  const name = overrides.name ?? "测试来源";
  return {
    id: `row-${name}`,
    name,
    price: null,
    currency: "CNY",
    lowest: false,
    price_status: null,
    provider_status: "success",
    data_provider: "fixture",
    data_freshness: "fresh",
    ...overrides,
  };
}

function deal(overrides: Partial<DealCardDto> = {}): DealCardDto {
  return {
    id: "deal_1",
    system_id: "sys_1",
    flight_no: "CA1835",
    platform: "飞猪",
    origin_city: "北京",
    origin_code: "BJS",
    destination_city: "上海",
    destination_code: "SHA",
    depart_date: "2026-08-01",
    airline: "CA",
    depart_time: "08:00",
    arrive_time: "10:00",
    duration_minutes: 120,
    stops: 0,
    price: 580,
    lowest_price: 580,
    tax: null,
    baggage_fee: null,
    has_baggage: null,
    total_price: 580,
    currency: "CNY",
    recommend_score: "9.5",
    winning_price_id: "row-飞猪",
    prices: [
      priceRow({ name: "飞猪", price: 580, price_status: "priced", lowest: true, data_provider: "flyai" }),
      priceRow({ name: "携程", provider_status: "loading", data_provider: "ctrip_snapshot" }),
    ],
    signals: [],
    data_freshness: "fresh",
    ...overrides,
  };
}

function response(text: string, result = deal()): ChatSearchResponse {
  return {
    session_id: "s_first",
    deals: [result],
    recommendation: { text },
  };
}

function results(sequence: number, result = deal()): SearchStreamEvent {
  return {
    type: "results",
    search_id: "server_search",
    sequence,
    payload: { deals: [result] },
  };
}

function complete(sequence: number, finalResponse: ChatSearchResponse): SearchStreamEvent {
  return {
    type: "complete",
    search_id: "server_search",
    sequence,
    payload: { response: finalResponse },
  };
}

async function send(message: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: message } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
  await waitFor(() => expect(calls.length).toBeGreaterThan(0));
}

function submit(message: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: message } });
  fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
}

beforeEach(() => {
  calls.length = 0;
  streamMock.mockReset();
  streamMock.mockImplementation(
    (_body, onEvent, signal) =>
      new Promise<ChatSearchResponse | null>((resolve, reject) => {
        calls.push({ onEvent, signal, resolve, reject });
      })
  );
});

test("chat page updates its card when results arrive before the stream completes", async () => {
  render(<ChatPage />);
  await send("从北京出发");

  expect(searchApi.stream).toHaveBeenCalledWith(
    { message: "从北京出发", session_id: null },
    expect.any(Function),
    expect.any(AbortSignal)
  );

  await act(async () => {
    calls[0].onEvent(results(2));
  });

  expect((await screen.findAllByText("飞猪")).length).toBeGreaterThan(0);
  expect(screen.getByText("正在获取数据")).toBeInTheDocument();
  expect(screen.queryByText("飞猪当前价格更优")).not.toBeInTheDocument();

  await act(async () => {
    calls[0].onEvent(complete(3, response("飞猪当前价格更优", deal({
      prices: [
        priceRow({ name: "飞猪", price: 580, price_status: "priced", lowest: true, data_provider: "flyai" }),
        priceRow({ name: "携程", provider_status: "queued", data_provider: "ctrip_snapshot" }),
      ],
    }))));
    calls[0].resolve(response("不应覆盖 canonical complete"));
  });

  expect(await screen.findByText("飞猪当前价格更优")).toBeInTheDocument();
  expect(screen.getByText("等待下次刷新")).toBeInTheDocument();
  expect(screen.queryByText("不应覆盖 canonical complete")).not.toBeInTheDocument();
});

test("uses the deal currency in fallback assistant copy", async () => {
  render(<ChatPage />);
  await send("上海到新加坡");
  const usdDeal = deal({
    price: 80,
    total_price: 80,
    currency: "USD",
    recommend_score: null,
    prices: [priceRow({ name: "Global Seller", price: 80, currency: "USD", price_status: "priced", lowest: true })],
  });

  await act(async () => {
    calls[0].onEvent(
      complete(1, {
        session_id: "s_usd",
        deals: [usdDeal],
      })
    );
  });

  expect(
    await screen.findByText("为您找到 1 个航班，最低价 US$80")
  ).toBeInTheDocument();
  expect(screen.queryByText("为您找到 1 个航班，最低价 ¥80")).not.toBeInTheDocument();
});

test("aborts and settles the old assistant while ignoring its late events", async () => {
  render(<ChatPage />);
  await send("旧搜索");
  await send("新搜索");

  expect(calls).toHaveLength(2);
  expect(calls[0].signal?.aborted).toBe(true);
  expect(screen.getByText("已取消本次搜索。")).toBeInTheDocument();
  expect(screen.getAllByText("正在为您深度扫描全网特价资源...")).toHaveLength(1);

  await act(async () => {
    calls[0].onEvent(results(2, deal({ prices: [priceRow({ name: "旧平台", price: 580, price_status: "priced" })] })));
    calls[1].onEvent(results(2, deal({ prices: [priceRow({ name: "新平台", price: 580, price_status: "priced" })] })));
  });

  expect(screen.queryByText("旧平台")).not.toBeInTheDocument();
  expect(screen.getByText("新平台")).toBeInTheDocument();
  expect(screen.getByText("已取消本次搜索。")).toBeInTheDocument();
});

test("aborts the active stream when unmounted", async () => {
  const { unmount } = render(<ChatPage />);
  await send("卸载搜索");

  unmount();

  expect(calls[0].signal?.aborted).toBe(true);
});

test("renders validation errors as a terminal assistant message", async () => {
  render(<ChatPage />);
  await send("过去日期");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "出发日期必须晚于今天" },
    });
    calls[0].resolve(null);
  });

  expect(await screen.findByText("出发日期必须晚于今天")).toBeInTheDocument();
  expect(screen.queryByText("正在为您深度扫描全网特价资源...")).not.toBeInTheDocument();
});

test("keeps validation feedback while accepting its canonical session for the next turn", async () => {
  render(<ChatPage />);
  await send("过去日期");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "出发日期必须晚于今天" },
    });
    calls[0].onEvent(complete(2, {
      session_id: "s_validation",
      deals: [],
      recommendation: { text: "无意义的空结果" },
    }));
  });

  expect(await screen.findByText("出发日期必须晚于今天")).toBeInTheDocument();
  expect(screen.queryByText("无意义的空结果")).not.toBeInTheDocument();

  await send("改成下周出发");

  expect(searchApi.stream).toHaveBeenLastCalledWith(
    { message: "改成下周出发", session_id: "s_validation" },
    expect.any(Function),
    expect.any(AbortSignal)
  );
});

test("serializes an immediate validation followup until canonical completion saves its session", async () => {
  render(<ChatPage />);
  await send("过去日期");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "请补充出发日期" },
    });
  });

  submit("下周一出发");

  expect(calls).toHaveLength(1);
  expect(calls[0].signal?.aborted).toBe(false);
  expect(screen.getByText("请补充出发日期")).toBeInTheDocument();
  expect(screen.queryByText("已取消本次搜索。")).not.toBeInTheDocument();

  await act(async () => {
    calls[0].onEvent(complete(2, {
      session_id: "s_validation_followup",
      deals: [],
      recommendation: { text: "不应覆盖校验提示" },
    }));
    calls[0].resolve(null);
  });

  await waitFor(() => expect(calls).toHaveLength(2));
  expect(searchApi.stream).toHaveBeenLastCalledWith(
    { message: "下周一出发", session_id: "s_validation_followup" },
    expect.any(Function),
    expect.any(AbortSignal)
  );
  expect(screen.getAllByText("下周一出发")).toHaveLength(1);
  expect(screen.getByText("请补充出发日期")).toBeInTheDocument();
});

test("releases a queued validation followup after clean EOF", async () => {
  render(<ChatPage />);
  await send("缺少日期");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "请补充日期" },
    });
  });
  submit("补充下周日期");

  await act(async () => {
    calls[0].resolve(null);
  });

  await waitFor(() => expect(calls).toHaveLength(2));
  expect(screen.getByText("请补充日期")).toBeInTheDocument();
  expect(screen.getAllByText("补充下周日期")).toHaveLength(1);
});

test("releases a queued validation followup after stream error", async () => {
  render(<ChatPage />);
  await send("缺少目的地");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "请补充目的地" },
    });
  });
  submit("补充上海");

  await act(async () => {
    calls[0].reject(new Error("reader failed"));
  });

  await waitFor(() => expect(calls).toHaveLength(2));
  expect(screen.getByText("请补充目的地")).toBeInTheDocument();
  expect(screen.getAllByText("补充上海")).toHaveLength(1);
});

test("drops a queued validation followup when the chat unmounts", async () => {
  const { unmount } = render(<ChatPage />);
  await send("缺少返程日期");

  await act(async () => {
    calls[0].onEvent({
      type: "validation_error",
      search_id: "server_search",
      sequence: 1,
      payload: { message: "请补充返程日期" },
    });
  });
  submit("下周日返程");

  unmount();

  expect(calls[0].signal?.aborted).toBe(true);
  await act(async () => {
    calls[0].onEvent(complete(2, response("卸载后不应继续")));
    calls[0].resolve(null);
  });
  expect(calls).toHaveLength(1);
});

test("finalizes partial provider rows before replacing an active search", async () => {
  render(<ChatPage />);
  await send("先查北京上海");

  await act(async () => {
    calls[0].onEvent(results(2, deal({
      prices: [
        priceRow({ name: "飞猪", price: 580, price_status: "priced", lowest: true, data_provider: "flyai" }),
        priceRow({ name: "携程", provider_status: "loading", data_provider: "ctrip_snapshot" }),
        priceRow({ name: "国际卖家", provider_status: "loading", data_provider: "serpapi_google_flights" }),
      ],
    })));
  });

  await send("再查北京广州");

  expect(calls[0].signal?.aborted).toBe(true);
  expect(screen.getByText("已保留当前报价，其余来源已停止更新。")).toBeInTheDocument();
  expect(screen.getByText("等待下次刷新")).toBeInTheDocument();
  expect(screen.getByText("暂时超时")).toBeInTheDocument();
  expect((await screen.findAllByText("飞猪")).length).toBeGreaterThan(0);
});

test("does not cancel a completed assistant while its stream promise is still settling", async () => {
  render(<ChatPage />);
  await send("已完成的搜索");

  await act(async () => {
    calls[0].onEvent(complete(2, response("已完成推荐")));
  });

  await send("新的搜索");

  expect(calls[0].signal?.aborted).toBe(false);
  expect(screen.getByText("已完成推荐")).toBeInTheDocument();
  expect(screen.queryByText("已取消本次搜索。")).not.toBeInTheDocument();
  expect(screen.getAllByText("正在为您深度扫描全网特价资源...")).toHaveLength(1);
});

test("does not apply a stale complete returned after an out-of-order event", async () => {
  render(<ChatPage />);
  await send("乱序搜索");

  await act(async () => {
    calls[0].onEvent(results(2, deal({ prices: [priceRow({ name: "最新结果", price: 580, price_status: "priced" })] })));
    calls[0].onEvent(complete(1, response("过期 complete", deal({ prices: [priceRow({ name: "过期结果", price: 580, price_status: "priced" })] }))));
    calls[0].resolve(response("返回值不应绕过 sequence", deal({ prices: [priceRow({ name: "返回值旧结果", price: 580, price_status: "priced" })] })));
  });

  expect(await screen.findByText("最新结果")).toBeInTheDocument();
  expect(screen.queryByText("过期 complete")).not.toBeInTheDocument();
  expect(screen.queryByText("返回值不应绕过 sequence")).not.toBeInTheDocument();
});

test("settles a clean EOF without complete instead of leaving a spinner", async () => {
  render(<ChatPage />);
  await send("EOF 搜索");

  await act(async () => {
    calls[0].resolve(null);
  });

  expect(await screen.findByText("搜索未完整结束，请重试。")).toBeInTheDocument();
  expect(screen.queryByText("正在为您深度扫描全网特价资源...")).not.toBeInTheDocument();
});

test("preserves canonical complete data when the stream rejects afterwards", async () => {
  render(<ChatPage />);
  await send("完成后异常");

  await act(async () => {
    calls[0].onEvent(results(2));
    calls[0].onEvent(complete(3, response("canonical 完成")));
    calls[0].reject(new Error("reader failed after complete"));
  });

  expect(await screen.findByText("canonical 完成")).toBeInTheDocument();
  expect(screen.queryByText("搜索失败，请检查网络后重试。")).not.toBeInTheDocument();
  expect((await screen.findAllByText("飞猪")).length).toBeGreaterThan(0);
});
