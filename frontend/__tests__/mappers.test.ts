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
    flight_no: "MU5137",
    platform: "flyai",
    origin_city: "北京",
    origin_code: "PEK",
    destination_city: "上海",
    destination_code: "SHA",
    depart_date: "2026-08-01",
    airline: "MU",
    depart_time: "08:00",
    arrive_time: "10:30",
    duration_minutes: 150,
    stops: 0,
    price: null,
    lowest_price: null,
    tax: null,
    baggage_fee: null,
    has_baggage: null,
    total_price: null,
    currency: "CNY",
    recommend_score: "8.6",
    winning_price_id: null,
    prices: [
      {
        id: "flyai-live-cny",
        name: "飞猪",
        price: null,
        currency: "CNY",
        price_status: "view_live_price",
        provider_status: "success",
        url: "https://example.com/book",
        data_provider: "flyai",
        data_freshness: "fresh",
      },
    ],
    signals: [],
    data_freshness: "fresh",
  });

  expect(card.basePrice).toBeNull();
  expect(card.tax).toBeNull();
  expect(card.baggageFee).toBeNull();
  expect(card.hasBaggage).toBeNull();
  expect(card.prices[0].price).toBeNull();
  expect(card.currency).toBe("CNY");
  expect(card.recommendScore).toBe("8.6");
  expect(card.stops).toBe(0);
});

test("preserves a nullable score and per-row currencies", () => {
  const card = dealToCardProps({
    id: "deal-usd",
    system_id: "system-usd",
    flight_no: "SQ833",
    platform: "Global Seller",
    origin_city: "上海",
    origin_code: "SHA",
    destination_city: "新加坡",
    destination_code: "SIN",
    depart_date: "2099-08-01",
    airline: "Fixture Air",
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
        url: "https://global.example.test/book",
        data_provider: "serpapi_google_flights",
        data_freshness: "fresh",
      },
    ],
    signals: [],
    booking_url: "https://global.example.test/book",
    data_freshness: "fresh",
  });

  expect(card.currency).toBe("USD");
  expect(card.prices[0].currency).toBe("USD");
  expect(card.recommendScore).toBeUndefined();
  expect(card.totalPrice).toBe(80);
  expect(card.winningPriceId).toBe("serpapi-global-usd");
  expect(card.dataFreshness).toBe("fresh");
});
