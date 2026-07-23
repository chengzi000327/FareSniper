import React from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { DiscoveryCardContent } from "@/components/discovery-card-content";
import type { PriceItem } from "@/lib/api";

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

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

test("renders source states without fake zeroes", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={null}
      totalPrice={null}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[
        priceRow({
          name: "飞猪",
          price: null,
          price_status: "view_live_price",
          url: "https://fly.test",
        }),
        priceRow({ name: "携程", provider_status: "loading" }),
      ]}
    />
  );

  expect(screen.getByText("查看实时价")).toHaveAttribute("href", "https://fly.test");
  expect(screen.getByText("正在获取数据")).toBeInTheDocument();
  expect(screen.getByText("平台未返回行李额度，请在预订页确认")).toBeInTheDocument();
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
});

test("uses mobile type density without changing the original card sections", () => {
  const { container } = render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2026-07-24"
      basePrice={500}
      totalPrice={700}
      tax={200}
      taxSource="regulatory_estimate"
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[]}
      compact
      narrow
    />
  );

  expect(container.firstElementChild).toHaveClass("p-2.5");
  expect(screen.getByRole("heading", { name: "北京" })).toHaveClass("text-sm");
  expect(screen.getByText("¥500")).toHaveClass("text-xs");
  expect(screen.getByText("平台展示价")).toHaveClass("text-[9px]");
  expect(screen.getByText("平台未返回行李额度，请在预订页确认")).toHaveClass("text-[10px]");
  expect(screen.getByText("多端价格参考")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "监控价格" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeInTheDocument();
});

test("renders a numeric view-live-price row as its known amount", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={null}
      totalPrice={null}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[
        priceRow({
          name: "飞猪",
          price: 500,
          price_status: "view_live_price",
          url: "https://fly.test",
        }),
      ]}
    />
  );

  const row = screen.getByText("飞猪").parentElement!;
  expect(within(row).getByText("¥500")).toBeInTheDocument();
  expect(within(row).queryByText("查看实时价")).not.toBeInTheDocument();
});

test("renders a neutral header for landing placeholders", () => {
  render(
    <DiscoveryCardContent
      from="上海"
      to="三亚"
      basePrice={null}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[priceRow({ name: "飞猪", provider_status: "loading" })]}
      placeholder
    />
  );

  expect(screen.getByText("待查询 · 正在获取数据")).toBeInTheDocument();
  expect(screen.queryByText(/直飞特惠/)).not.toBeInTheDocument();
  expect(screen.queryByText(/实时价格/)).not.toBeInTheDocument();
});

test("labels an incomplete fee breakdown as a platform display price", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      winningPriceId="winner"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "winner",
          name: "飞猪",
          price: 580,
          lowest: true,
          price_status: "priced",
          data_provider: "flyai",
        }),
      ]}
    />
  );

  expect(screen.getByText("平台展示价")).toBeInTheDocument();
  expect(screen.getByText(/机建燃油与行李额度待平台补充/)).toBeInTheDocument();
  expect(screen.queryByText("综合总价")).not.toBeInTheDocument();
});

test("labels a complete fee breakdown as a confirmed total", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={500}
      totalPrice={580}
      tax={80}
      taxSource="regulatory_estimate"
      baggageFee={0}
      baggageAllowance="20KG"
      hasBaggage={true}
      currency="CNY"
      platform="飞猪"
      winningPriceId="winner"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "winner",
          name: "飞猪",
          price: 580,
          lowest: true,
          price_status: "priced",
          data_provider: "flyai",
        }),
      ]}
    />
  );

  expect(screen.getByText("综合总价")).toBeInTheDocument();
  expect(screen.getByText("机建燃油（现行）")).toBeInTheDocument();
  expect(screen.getByText("20KG")).toBeInTheDocument();
  expect(screen.getByText(/按现行标准计算的机建燃油/)).toBeInTheDocument();
  expect(screen.getByText("¥80")).toBeInTheDocument();
  expect(screen.getByText("含免费托运行李 20KG")).toBeInTheDocument();
});

test("does not confirm a fee breakdown when the platform total is inconsistent", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={400}
      totalPrice={650}
      tax={70}
      baggageFee={30}
      hasBaggage={true}
      currency="CNY"
      platform="飞猪"
      winningPriceId="winner"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "winner",
          name: "飞猪",
          price: 650,
          lowest: true,
          price_status: "priced",
          data_provider: "flyai",
        }),
      ]}
    />
  );

  expect(screen.getByText("平台展示价")).toBeInTheDocument();
  expect(screen.getByText(/机建燃油与行李额度待平台补充/)).toBeInTheDocument();
  expect(screen.queryByText("综合总价")).not.toBeInTheDocument();
});

test("renders every terminal provider state and rejects non-HTTPS live links", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[
        priceRow({ name: "排队", provider_status: "queued" }),
        priceRow({ name: "过期", provider_status: "stale" }),
        priceRow({ name: "超时", provider_status: "timeout" }),
        priceRow({ name: "未配置", provider_status: "disabled" }),
        priceRow({ name: "错误", provider_status: "error" }),
        priceRow({ name: "无结果", provider_status: "empty" }),
        priceRow({ name: "不安全链接", price_status: "view_live_price", url: "http://fly.test" }),
      ]}
    />
  );

  ["等待下次刷新", "价格可能已更新", "暂时超时", "尚未配置", "暂时不可用", "暂无结果"].forEach(
    (label) => expect(screen.getByText(label)).toBeInTheDocument()
  );
  expect(screen.queryByText("查看实时价")).not.toBeInTheDocument();
  expect(screen.queryByText("最低")).not.toBeInTheDocument();
});

test("only renders a clickable booking action for a parseable HTTPS URL", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      tax={0}
      baggageFee={0}
      hasBaggage
      currency="CNY"
      platform="飞猪"
      bookingUrl="javascript:alert(1)"
      prices={[]}
    />
  );

  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("does not describe unknown or excluded baggage as free", () => {
  const { rerender } = render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      tax={0}
      baggageFee={0}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[]}
    />
  );

  expect(screen.queryByText("免费")).not.toBeInTheDocument();
  expect(screen.getByText("平台未返回行李额度，请在预订页确认")).toBeInTheDocument();

  rerender(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      tax={0}
      baggageFee={0}
      hasBaggage={false}
      currency="CNY"
      platform="飞猪"
      prices={[]}
    />
  );

  expect(screen.queryByText("免费")).not.toBeInTheDocument();
  expect(screen.getByText("不含")).toBeInTheDocument();
});

test("keeps a known baggage surcharge visible when free baggage is excluded", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      tax={20}
      baggageFee={50}
      hasBaggage={false}
      currency="CNY"
      platform="飞猪"
      prices={[]}
    />
  );

  expect(screen.getByText("+¥50")).toBeInTheDocument();
  expect(screen.getByText(/需加购 ¥50，已计入总价/)).toBeInTheDocument();
  expect(screen.getByText("¥650")).toBeInTheDocument();
  expect(screen.queryByText("免费")).not.toBeInTheDocument();
});

test("limits lowest-price claims to a known realtime lowest offer", () => {
  const { rerender } = render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={null}
      totalPrice={null}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      prices={[priceRow({ name: "飞猪", price_status: "view_live_price", lowest: true, url: "https://fly.test" })]}
    />
  );

  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
  expect(screen.queryByText(/全网.*最优解/)).not.toBeInTheDocument();

  rerender(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      totalPrice={580}
      tax={0}
      baggageFee={0}
      hasBaggage
      currency="CNY"
      platform="飞猪"
      winningPriceId="row-飞猪"
      dataFreshness="fresh"
      prices={[priceRow({ name: "飞猪", price: 580, price_status: "priced", lowest: true })]}
    />
  );

  expect(screen.getByText("实时底价")).toBeInTheDocument();
  expect(
    screen.getByText((_, element) => element?.tagName === "P" && element.textContent?.includes("最优解") === true)
  ).toBeInTheDocument();
});

test("uses the backend winning row for badge, seller copy, and booking action", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-01"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      bookingUrl="https://fly.example.test/book"
      winningPriceId="live-flyai"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "snapshot-ctrip",
          name: "携程",
          price: 500,
          lowest: true,
          data_provider: "ctrip_snapshot",
        }),
        priceRow({
          id: "live-flyai",
          name: "飞猪",
          price: 580,
          lowest: false,
          price_status: "priced",
          url: "https://fly.example.test/book",
          data_provider: "flyai",
        }),
      ]}
    />
  );

  const liveSeller = screen
    .getAllByText("飞猪")
    .find((element) => element.classList.contains("text-sm"));
  const liveRow = liveSeller?.parentElement ?? null;
  const snapshotRow = screen.getByText("携程").parentElement;
  expect(liveRow).not.toBeNull();
  expect(snapshotRow).not.toBeNull();
  expect(within(liveRow!).getByText("最低")).toBeInTheDocument();
  expect(within(snapshotRow!).queryByText("最低")).not.toBeInTheDocument();
  expect(
    screen.getByText((_, element) =>
      element?.tagName === "P" && element.textContent?.includes("飞猪") === true
    )
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "前往预订" })).toHaveAttribute(
    "href",
    "https://fly.example.test/book"
  );
});

test("shows the platform quote in the ticket-price field for legacy offers without a base-price split", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="长治"
      date="2026-07-24"
      basePrice={null}
      totalPrice={250}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="携程"
      prices={[]}
    />
  );

  expect(screen.getAllByText("¥250")).toHaveLength(2);
  expect(
    screen.getByText(/票价栏暂按平台展示价显示/)
  ).toBeInTheDocument();
});

test("renders a stale Ctrip winner without realtime copy", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-01"
      basePrice={500}
      totalPrice={500}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="携程"
      bookingUrl="https://ctrip.example.test/book"
      winningPriceId="ctrip-stale-cny"
      dataFreshness="stale"
      inventoryExpiresAt="2000-01-01T00:00:00+00:00"
      prices={[
        priceRow({
          id: "ctrip-stale-cny",
          name: "携程",
          price: 500,
          lowest: true,
          price_status: "stale",
          provider_status: "stale",
          data_provider: "ctrip_snapshot",
          data_freshness: "stale",
          url: "https://ctrip.example.test/book",
          expires_at: "2000-01-01T00:00:00+00:00",
        }),
        priceRow({
          id: "live-flyai",
          name: "飞猪",
          price: 560,
          price_status: "priced",
          provider_status: "success",
          data_provider: "flyai",
          data_freshness: "fresh",
        }),
      ]}
    />
  );

  expect(within(screen.getByText("携程").parentElement!).getByText("¥500")).toBeInTheDocument();
  expect(screen.getByText("¥560")).toBeInTheDocument();
  expect(within(screen.getByText("携程").parentElement!).getByText("最低")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "前往预订" })).toHaveAttribute(
    "href",
    "https://ctrip.example.test/book",
  );
  expect(screen.queryByText("价格可能已更新")).not.toBeInTheDocument();
  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
});

test("does not select a stale Ctrip winner without an HTTPS row URL", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={500}
      totalPrice={500}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="携程"
      bookingUrl="https://ctrip.example.test/book"
      winningPriceId="ctrip-stale-cny"
      dataFreshness="stale"
      prices={[
        priceRow({
          id: "ctrip-stale-cny",
          name: "携程",
          price: 500,
          lowest: true,
          price_status: "stale",
          provider_status: "stale",
          data_provider: "ctrip_snapshot",
          data_freshness: "stale",
          url: "http://ctrip.example.test/book",
        }),
      ]}
    />
  );

  const row = screen.getByText("携程").parentElement!;
  expect(within(row).queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("keeps a numeric unknown-freshness row visible without realtime claims", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-01"
      basePrice={500}
      totalPrice={500}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="携程"
      bookingUrl="https://booking.example.test/unknown"
      winningPriceId="unknown-row"
      dataFreshness="unknown"
      prices={[
        priceRow({
          id: "unknown-row",
          name: "携程",
          price: 500,
          lowest: true,
          url: "https://booking.example.test/unknown",
          data_freshness: "unknown",
          data_provider: "legacy",
        }),
      ]}
    />
  );

  expect(within(screen.getByText("携程").parentElement!).getByText("¥500")).toBeInTheDocument();
  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
  expect(screen.queryByText(/最优解/)).not.toBeInTheDocument();
  expect(screen.queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("does not select an expired fresh FlyAI winner", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-01"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      bookingUrl="https://booking.example.test/expired"
      winningPriceId="expired-row"
      inventoryExpiresAt="2000-01-01T00:00:00+00:00"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "expired-row",
          name: "飞猪",
          price: 580,
          lowest: true,
          price_status: "priced",
          url: "https://booking.example.test/expired",
          data_freshness: "fresh",
          data_provider: "flyai",
        }),
      ]}
    />
  );

  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
  expect(screen.queryByText(/最优解/)).not.toBeInTheDocument();
  expect(screen.queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("does not select an expired fresh SerpAPI winner", () => {
  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-01"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="Google Flights"
      bookingUrl="https://booking.example.test/expired-serpapi"
      winningPriceId="expired-serpapi"
      inventoryExpiresAt="2099-08-02T00:00:00+00:00"
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "expired-serpapi",
          name: "Google Flights",
          price: 580,
          lowest: true,
          price_status: "priced",
          url: "https://booking.example.test/expired-serpapi",
          data_provider: "serpapi_google_flights",
          data_freshness: "fresh",
          expires_at: "2000-01-01T00:00:00+00:00",
        }),
      ]}
    />
  );

  expect(screen.queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("rerenders at expiry and gates realtime winner and row links while mounted", () => {
  vi.useFakeTimers();
  const now = new Date("2099-08-01T00:00:00+00:00");
  const expiry = new Date(now.getTime() + 1_000).toISOString();
  vi.setSystemTime(now);

  render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      date="2099-08-02"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      bookingUrl="https://booking.example.test/winner"
      winningPriceId="winner"
      inventoryExpiresAt={expiry}
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "winner",
          name: "飞猪",
          price: 580,
          lowest: true,
          price_status: "priced",
          url: "https://booking.example.test/winner",
          expires_at: expiry,
        }),
        priceRow({
          id: "live-row",
          name: "实时查询",
          price_status: "view_live_price",
          url: "https://booking.example.test/live",
          expires_at: expiry,
        }),
      ]}
    />
  );

  expect(screen.getByText("实时底价")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "前往预订" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看实时价" })).toBeInTheDocument();

  act(() => {
    vi.advanceTimersByTime(1_000);
  });

  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "查看实时价" })).not.toBeInTheDocument();
});

test("rechecks expiry on focus and visibility and cleans lifecycle resources", () => {
  vi.useFakeTimers();
  const now = new Date("2099-08-01T00:00:00+00:00");
  const expiry = new Date(now.getTime() + 60_000).toISOString();
  vi.setSystemTime(now);
  const removeWindowListener = vi.spyOn(window, "removeEventListener");
  const removeDocumentListener = vi.spyOn(document, "removeEventListener");

  const { unmount } = render(
    <DiscoveryCardContent
      from="北京"
      to="上海"
      basePrice={580}
      totalPrice={580}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="CNY"
      platform="飞猪"
      bookingUrl="https://booking.example.test/winner"
      winningPriceId="winner"
      inventoryExpiresAt={expiry}
      dataFreshness="fresh"
      prices={[
        priceRow({
          id: "winner",
          name: "飞猪",
          price: 580,
          lowest: true,
          price_status: "priced",
          url: "https://booking.example.test/winner",
          expires_at: expiry,
        }),
      ]}
    />
  );

  expect(screen.getByText("实时底价")).toBeInTheDocument();
  expect(vi.getTimerCount()).toBe(1);
  vi.setSystemTime(new Date(now.getTime() + 60_000));
  fireEvent.focus(window);
  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();

  fireEvent(document, new Event("visibilitychange"));
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
  expect(vi.getTimerCount()).toBe(0);

  unmount();

  expect(vi.getTimerCount()).toBe(0);
  expect(removeWindowListener).toHaveBeenCalledWith("focus", expect.any(Function));
  expect(removeDocumentListener).toHaveBeenCalledWith(
    "visibilitychange",
    expect.any(Function)
  );
});

test("formats each currency with Intl and does not fabricate a score", () => {
  const usd = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(80);

  render(
    <DiscoveryCardContent
      from="上海"
      to="新加坡"
      basePrice={80}
      totalPrice={80}
      tax={null}
      baggageFee={null}
      hasBaggage={null}
      currency="USD"
      platform="Global Seller"
      prices={[
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
      ]}
    />
  );

  expect(screen.getAllByText(usd).length).toBeGreaterThan(0);
  expect(screen.queryByText("¥80")).not.toBeInTheDocument();
  expect(screen.queryByText("9.5")).not.toBeInTheDocument();
  expect(screen.queryByText("发现指数")).not.toBeInTheDocument();
});
