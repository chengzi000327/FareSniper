import React from "react";
import { render, screen } from "@testing-library/react";
import { DiscoveryCardContent } from "@/components/discovery-card-content";

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
      platform="飞猪"
      prices={[
        {
          name: "飞猪",
          price: null,
          status: "view_live_price",
          url: "https://fly.test",
        },
        { name: "携程", price: null, status: "loading" },
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
      platform="飞猪"
      prices={[{ name: "飞猪", price: null, status: "loading" }]}
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
      platform="飞猪"
      prices={[
        { name: "排队", price: null, status: "queued" },
        { name: "过期", price: null, status: "stale" },
        { name: "超时", price: null, status: "timeout" },
        { name: "未配置", price: null, status: "disabled" },
        { name: "错误", price: null, status: "error" },
        { name: "无结果", price: null, status: "empty" },
        { name: "不安全链接", price: null, status: "view_live_price", url: "http://fly.test" },
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
      platform="飞猪"
      prices={[{ name: "飞猪", price: null, status: "view_live_price", lowest: true, url: "https://fly.test" }]}
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
      platform="飞猪"
      prices={[{ name: "飞猪", price: 580, status: "success", lowest: true }]}
    />
  );

  expect(screen.getByText("实时底价")).toBeInTheDocument();
  expect(
    screen.getByText((_, element) => element?.tagName === "P" && element.textContent?.includes("最优解") === true)
  ).toBeInTheDocument();
});
