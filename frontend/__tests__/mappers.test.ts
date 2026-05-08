import { dealCardToDiscoveryCard } from "@/lib/mappers";

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
