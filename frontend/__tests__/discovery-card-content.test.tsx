import React from "react";
import { render, screen, within } from "@testing-library/react";
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
  expect(screen.getByText("行李额以预订页为准")).toBeInTheDocument();
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
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
  expect(screen.getByText("行李额以预订页为准")).toBeInTheDocument();

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

test("gates realtime copy and booking when inventory freshness is unknown", () => {
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

  expect(screen.getByText("更新时间未知")).toBeInTheDocument();
  expect(screen.queryByText("实时底价")).not.toBeInTheDocument();
  expect(screen.queryByText("全网多端实时同步")).not.toBeInTheDocument();
  expect(screen.queryByText(/最优解/)).not.toBeInTheDocument();
  expect(screen.queryByText("最低")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "前往预订" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "前往预订" })).not.toBeInTheDocument();
});

test("gates realtime copy and booking after the winning inventory expiry", () => {
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
