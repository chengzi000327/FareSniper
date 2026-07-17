import { dealCardToDiscoveryCard, dealToCardProps } from "@/lib/mappers";

test("maps base_price/tax/baggage_fee into props", () => {
  const card = dealCardToDiscoveryCard({
    flight_no: "MU5137",
    platform: "ctrip",
    price: 480,
    base_price: 380,
    tax: 80,
    baggage_fee: 20,
    origin: "BJS",
    destination: "SHA",
    depart_date: "2026-05-08",
    signals: ["历史低价"],
    recommend_score: 8.6,
  });
  expect(card.basePrice).toBe(380);
  expect(card.tax).toBe(80);
  expect(card.baggageFee).toBe(20);
  expect(card.signals).toContain("历史低价");
});

test("preserves null price and baggage fields when mapping a deal", () => {
  const card = dealToCardProps({
    id: "deal-1",
    system_id: "system-1",
    platform: "flyai",
    origin_city: "北京",
    origin_code: "PEK",
    destination_city: "上海",
    destination_code: "SHA",
    depart_date: "2026-08-01",
    airline: "MU",
    depart_time: "08:00",
    arrive_time: "10:30",
    price: null,
    tax: null,
    baggage_fee: null,
    has_baggage: null,
    total_price: null,
    currency: "CNY",
    recommend_score: "8.6",
    prices: [
      {
        name: "飞猪",
        price: null,
        status: "view_live_price",
        url: "https://example.com/book",
        data_provider: "flyai",
      },
    ],
    signals: [],
  });

  expect(card.basePrice).toBeNull();
  expect(card.tax).toBeNull();
  expect(card.baggageFee).toBeNull();
  expect(card.hasBaggage).toBeNull();
  expect(card.prices[0].price).toBeNull();
});
