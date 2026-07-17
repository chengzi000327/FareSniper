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
