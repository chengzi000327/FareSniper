import type { DealCardDto, PriceItem } from './api'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'
import type { DealCardDto as ApiDealCardDto, DiscoveryCardContent } from "@/types/api";

type NullableDiscoveryCardContentProps = Omit<
  DiscoveryCardContentProps,
  "basePrice" | "tax" | "baggageFee" | "hasBaggage" | "prices"
> & {
  basePrice: number | null;
  tax: number | null;
  baggageFee: number | null;
  hasBaggage: boolean | null;
  prices: PriceItem[];
};

export function dealToCardProps(deal: DealCardDto): DiscoveryCardContentProps {
  const card: NullableDiscoveryCardContentProps = {
    from: deal.origin_city,
    to: deal.destination_city,
    date: deal.depart_date,
    basePrice: deal.price,
    tax: deal.tax,
    baggageFee: deal.baggage_fee,
    hasBaggage: deal.has_baggage,
    platform: deal.platform,
    recommendScore: deal.recommend_score || undefined,
    prices: deal.prices,
    bookingUrl: deal.booking_url ?? null,
  }

  // Task 9 widens card props; this preserves transport nulls in the meantime.
  return card as unknown as DiscoveryCardContentProps
}

export function dealCardToDiscoveryCard(d: ApiDealCardDto): DiscoveryCardContent {
  return {
    flightNo: d.flight_no,
    platform: d.platform,
    price: d.price,
    basePrice: d.base_price,
    tax: d.tax,
    baggageFee: d.baggage_fee,
    origin: d.origin,
    destination: d.destination,
    departDate: d.depart_date,
    signals: d.signals ?? [],
    recommendScore: d.recommend_score ?? null,
    bookingUrl: d.booking_url ?? null,
  };
}
